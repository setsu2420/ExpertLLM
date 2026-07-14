"""LLM 服务 - 封装所有大语言模型调用逻辑"""
from __future__ import annotations

from typing import Dict, List, Generator, Tuple
import requests
import json
import time
from google import genai
from openai import OpenAI

import config
from services import metrics


class LLMService:
    def call_llm_deep(self, provider: str, model_name: str, messages: list, schema: dict = None) -> dict:
        """统一的 deep/schema 限制模式非流式调用入口，返回结构化 dict"""
        start = time.time()
        status = "success"
        try:
            if provider == "gemini":
                return self._call_gemini_deep(model_name, messages, schema=schema)
            elif provider == "gpt":
                return self._call_gpt_deep(model_name, messages, schema=schema)
            elif provider == "silicon":
                return self._call_silicon_deep(model_name, messages, schema=schema)
            else:
                status = "failure"
                raise ValueError(f"Unknown provider: {provider}")
        except Exception:
            status = "failure"
            raise
        finally:
            print(model_name+"=============")
            metrics.observe_llm_call(
                provider=provider,
                model=model_name,
                status=status,
                latency_seconds=time.time() - start,
            )
    """大语言模型服务"""
    
    def __init__(self):
        self.gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.gpt_client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.silicon_url = config.SILICON_URL
        self.silicon_key = f"Bearer {config.SILICON_KEY}"

    # --- 兼容助手：将多种返回结构统一为字符串 ---
    def _flatten_content(self, content) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(self._flatten_content(x) for x in content)
        if isinstance(content, dict):
            # 常见字段兜底
            for key in ("text", "content", "value"):
                if key in content:
                    return self._flatten_content(content[key])
            # OpenAI 新 content 格式：{"type": "output_text", "text": {"content": "..."}}
            if "type" in content and "text" in content:
                return self._flatten_content(content["text"])
            return ""
        # 对象：尝试属性访问
        text_attr = getattr(content, "text", None)
        if text_attr is not None:
            return self._flatten_content(text_attr)
        value_attr = getattr(content, "value", None)
        if value_attr is not None:
            return self._flatten_content(value_attr)
        return str(content)
    
    def call_llm(self, provider: str, model_name: str, messages: List[Dict[str, str]]) -> str:
        """调用 LLM（非流式）
        
        Args:
            provider: 提供商 (gemini/gpt/silicon)
            model_name: 模型名称
            messages: 消息历史
            
        Returns:
            模型回复内容
        """
        start = time.time()
        status = "success"
        try:
            if provider == "gemini":
                result = self._call_gemini(model_name, messages)
            elif provider == "gpt":
                result = self._call_gpt(model_name, messages)
            elif provider == "silicon":
                result = self._call_silicon(model_name, messages)
            else:
                status = "failure"
                raise ValueError(f"Unknown provider: {provider}")
            return result
        except Exception:
            status = "failure"
            raise
        finally:
            metrics.observe_llm_call(
                provider=provider,
                model=model_name,
                status=status,
                latency_seconds=time.time() - start,
            )
    
    def call_llm_stream(
        self, 
        provider: str, 
        model_name: str, 
        messages: List[Dict[str, str]]
    ) -> Generator[Tuple[str, str], None, None]:
        """调用 LLM（流式）
        
        Args:
            provider: 提供商 (gemini/gpt/silicon)
            model_name: 模型名称
            messages: 消息历史
            
        Yields:
            (content_char, reasoning_char) 元组，每次返回单个字符的增量
        """
        start = time.time()
        status = "success"
        try:
            if provider == "silicon":
                generator = self._call_silicon_stream(model_name, messages)
            elif provider == "gpt":
                generator = self._call_gpt_stream(model_name, messages)
            elif provider == "gemini":
                generator = self._call_gemini_stream(model_name, messages)
            else:
                status = "failure"
                raise ValueError(f"Unknown provider: {provider}")

            for chunk in generator:
                yield chunk
        except Exception:
            status = "failure"
            raise
        finally:
            print(model_name+"=============")
            metrics.observe_llm_call(
                provider=provider,
                model=model_name,
                status=status,
                latency_seconds=time.time() - start,
            )
    
    def _call_gemini(self, model_name: str, messages: List[Dict[str, str]]) -> str:
        """调用 Gemini API"""
        # 提取首个 system 提示词，前置到历史（Gemini 不接受 system_instruction 参数）
        system_prompt = None
        normal_messages: List[Dict[str, str]] = []
        for msg in messages:
            if msg.get("role") == "system" and system_prompt is None:
                system_prompt = msg.get("content", "")
                continue
            normal_messages.append(msg)

        gemini_history = []
        if system_prompt:
            gemini_history.append({"role": "user", "parts": [{"text": system_prompt}]})
        for msg in normal_messages:
            role = "user" if msg.get("role") == "user" else "model"
            gemini_history.append({
                "role": role, 
                "parts": [{"text": msg.get("content", "")}]
            })
        
        resp = self.gemini_client.models.generate_content(
            model=model_name, 
            contents=gemini_history
        )
        return getattr(resp, "text", "") or ""
    
    def _call_gpt(self, model_name: str, messages: List[Dict[str, str]]) -> str:
        """调用 GPT API"""
        resp = self.gpt_client.chat.completions.create(
            model=model_name,
            messages=messages,
            store=True
        )
        return self._flatten_content(resp.choices[0].message.content)
    
    def _call_silicon(self, model_name: str, messages: List[Dict[str, str]]) -> str:
        """调用 Silicon Flow API"""
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "max_tokens": 8192,
            "temperature": 0.7
        }
        headers = {
            "Authorization": self.silicon_key,
            "Content-Type": "application/json"
        }
        
        r = requests.post(self.silicon_url, json=payload, headers=headers, timeout=240)
        if r.status_code != 200:
            raise RuntimeError(f"SiliconFlow error: {r.status_code} - {r.text}")
        
        return self._flatten_content(r.json()["choices"][0]["message"].get("content"))
    
    def _call_silicon_stream(
        self, 
        model_name: str, 
        messages: List[Dict[str, str]]
    ) -> Generator[Tuple[str, str], None, None]:
        """调用 Silicon Flow API（流式）"""
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "max_tokens": 4096,
            "temperature": 0.7
        }
        headers = {
            "Authorization": self.silicon_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        r = requests.post(self.silicon_url, json=payload, headers=headers, stream=True, timeout=240)
        if r.status_code != 200:
            raise RuntimeError(f"SiliconFlow error: {r.status_code} - {r.text}")
        
        for line in r.iter_lines():
            if not line:
                continue
            s = line.decode("utf-8")
            if s.startswith("data: "):
                s = s[6:]
            if s.strip() == "[DONE]":
                break
            
            try:
                obj = json.loads(s)
            except json.JSONDecodeError:
                continue
            
            delta = (obj.get("choices") or [{}])[0].get("delta") or {}
            content = self._flatten_content(delta.get("content"))
            reasoning = self._flatten_content(delta.get("reasoning_content"))
            
            # 先输出思考过程，再输出正文
            for ch in reasoning:
                yield "", ch
            for ch in content:
                yield ch, ""
    
    def _call_gpt_stream(
        self, 
        model_name: str, 
        messages: List[Dict[str, str]]
    ) -> Generator[Tuple[str, str], None, None]:
        """调用 GPT API（流式）"""
        try:
            stream = self.gpt_client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True
            )
            
            for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                if not delta:
                    continue
                
                content = self._flatten_content(getattr(delta, "content", None))
                reasoning = self._flatten_content(
                    getattr(delta, "reasoning_content", None)
                    or getattr(delta, "reasoning", None)
                    or getattr(delta, "thought", None)
                )
                
                for ch in reasoning:
                    yield "", ch
                for ch in content:
                    yield ch, ""
        except Exception:
            # 回退到非流式
            text = self._call_gpt(model_name, messages)
            for ch in text:
                yield ch, ""
    
    def _call_gemini_stream(
        self, 
        model_name: str, 
        messages: List[Dict[str, str]]
    ) -> Generator[Tuple[str, str], None, None]:
        """调用 Gemini API（流式）"""
        try:
            system_prompt = None
            normal_messages: List[Dict[str, str]] = []
            for msg in messages:
                if msg.get("role") == "system" and system_prompt is None:
                    system_prompt = msg.get("content", "")
                    continue
                normal_messages.append(msg)

            gemini_history = []
            if system_prompt:
                gemini_history.append({"role": "user", "parts": [{"text": system_prompt}]})
            for msg in normal_messages:
                role = "user" if msg.get("role") == "user" else "model"
                gemini_history.append({
                    "role": role,
                    "parts": [{"text": msg.get("content", "")}]
                })
            
            stream = self.gemini_client.models.generate_content_stream(
                model=model_name,
                contents=gemini_history
            )
            
            for chunk in stream:
                text = getattr(chunk, "text", "") or ""
                for ch in text:
                    yield ch, ""
        except Exception:
            # 回退到非流式
            text = self._call_gemini(model_name, messages)
            for ch in text:
                yield ch, ""

    def _call_silicon_deep(
            self, 
            model_name: str, 
            messages: List[Dict[str, str]], 
            schema: dict = None) -> dict:
        """调用 Silicon Flow API，返回 content 字段已解析为字典，支持 schema 限制（非流式，无 reasoning）"""
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "max_tokens": 4096,
            "temperature": 0.7
        }
        # 使用 SiliconFlow/OpenAI-compatible response_format JSON schema
        # 参考 SDK 示例：response_format={"type":"json_schema","json_schema":{"name":"...","schema": json_schema}}
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": schema
                }
            }
        headers = {
            "Authorization": self.silicon_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        r = requests.post(self.silicon_url, json=payload, headers=headers)
        if r.status_code != 200:
            raise RuntimeError(f"SiliconFlow error: {r.status_code} - {r.text}")
        content = r.json()["choices"][0]["message"].get("content")
        if isinstance(content, dict):
            return content
        try:
            return json.loads(content)
        except Exception:
            return {"raw": content}

    def _call_gpt_deep(self, model_name: str, messages: List[Dict[str, str]], schema: dict = None) -> dict:
        """调用 GPT API，支持 function/schema 限制，返回 content 字段已解析为字典（非流式，无 reasoning）"""
        params = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "temperature": 0.7
        }
        if schema is not None:
            params["response_format"] = {"type": "json_object", "schema": schema}
        resp = self.gpt_client.chat.completions.create(**params)
        content = resp.choices[0].message.content
        if isinstance(content, dict):
            return content
        try:
            return json.loads(content)
        except Exception:
            return {"raw": content}

    def _call_gemini_deep(self, model_name: str, messages: List[Dict[str, str]], schema: dict = None, tools: list = None) -> dict:
        """调用 Gemini API，支持 response_json_schema，返回 content 字段已解析为字典（非流式，无 reasoning）"""
        # 组装 config
        config_args = {}
        if tools:
            config_args["tools"] = tools
        if schema is not None:
            config_args["response_mime_type"] = "application/json"
            config_args["response_json_schema"] = schema
        # 组装 gemini_history
        system_prompt = None
        normal_messages: List[dict] = []
        for msg in messages:
            if msg.get("role") == "system" and system_prompt is None:
                system_prompt = msg.get("content", "")
                continue
            normal_messages.append(msg)
        gemini_history = []
        if system_prompt:
            gemini_history.append({"role": "user", "parts": [{"text": system_prompt}]})
        for msg in normal_messages:
            role = "user" if msg.get("role") == "user" else "model"
            gemini_history.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}]})
        resp = self.gemini_client.models.generate_content(
            model=model_name,
            contents=gemini_history,
            config=config_args if config_args else None
        )
        text = getattr(resp, "text", "") or ""
        if isinstance(text, dict):
            return text
        try:
            return json.loads(text)
        except Exception:
            return {"raw": text}

    
# 全局单例
llm_service = LLMService()
