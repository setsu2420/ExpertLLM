"""聊天路由 - 聊天、会话管理"""
import json
from flask import Blueprint, request, jsonify, session, Response, stream_with_context

import logging
import os, time
import re
import db_service
import config
from services.llm_service import llm_service
from services.chat_service import chat_service
from services.sensitive_filter import get_filter
from utils.decorators import login_required

from services.schema import AnswerTotal, AnswerInitial, AnswerEnd


chat_bp = Blueprint('chat', __name__, url_prefix='/api')


@chat_bp.route("/session/new", methods=["POST"])
@login_required
def new_session():
    """创建新会话"""
    current_user_id = session.get('user_id')
    session_id = chat_service.create_new_session(user_id=current_user_id)
    return jsonify({"status": "success", "session_id": session_id})


@chat_bp.route("/chat/stream", methods=["POST"])
@login_required
def chat_stream():
    """
    聊天接口（流式）
    -------------------
    前端通过 POST /api/chat/stream 请求大模型流式输出（如逐字/逐句返回）。
    
    前端需传递参数：
        - session_id: 当前会话ID（字符串，必填）
        - turn_id: 本轮对话ID（字符串，必填）
        - prompt: 用户输入内容（字符串，必填）
        - provider: 大模型提供方（如 'gpt', 'gemini', 'silicon'，必填）
        - model: 具体模型名（如 'gpt-3.5-turbo'，必填）
        - model_key: 模型标识（如 'gpt'，必填）
        - selected_models: 选择的模型列表（数组，可选）
        - serial_index: 当前模型在本轮中的顺序编号（int，可选）
    
    处理流程：
        1. 校验参数，敏感词检查。
        2. 获取会话锁，确保 session/record 存在。
        3. 保存用户输入到数据库（turn、thread）。
        4. 获取上下文历史，插入系统提示词。
        5. 通过 llm_service.call_llm_stream() 调用大模型API，边生成边返回。
        6. 以 NDJSON 流式返回：meta（元信息）、delta（增量内容）、done、error 事件。
        7. 结束后保存大模型回复到数据库。
    
    返回：
        - mimetype: application/x-ndjson
        - 每行一个 JSON 事件：
            {"event": "meta", ...}  # 首行，包含模型/会话信息
            {"event": "delta", "delta": "新内容", "reasoning_delta": "推理内容"}
            {"event": "done"}        # 结束
            {"event": "error", "content": "错误信息"}  # 若有异常
    """
    current_user_id = session.get('user_id')
    data = request.json or {}

    session_id = (data.get("session_id") or "").strip()
    turn_id = (data.get("turn_id") or "").strip()
    prompt = (data.get("prompt") or "").strip()


    provider = (data.get("provider") or "").strip()
    model_name = (data.get("model") or "").strip()
    model_key = (data.get("model_key") or "").strip()
    selected_models = data.get("selected_models") or []
    if not isinstance(selected_models, list):
        selected_models = []


    # 一系列验证
    # 参数验证
    if not session_id or not turn_id or not prompt:
        return jsonify({
            "status": "error",
            "content": "Missing session_id/turn_id/prompt"
        }), 400
    if provider not in {"gemini", "gpt", "silicon"}:
        return jsonify({"status": "error", "content": "Unknown provider"}), 400
    if not model_name or not model_key:
        return jsonify({"status": "error", "content": "Missing model/model_key"}), 400  
    # 敏感词检查
    if get_filter is not None:
        try:
            sensitive_filter = get_filter()
            is_sensitive, sensitive_word, _ = sensitive_filter.detect(prompt)
            if is_sensitive:
                return jsonify({
                    "status": "error",
                    "content": f"输入包含敏感词汇，已被拦截。请修改后重新提问。",
                    "sensitive_word": sensitive_word
                }), 403
        except Exception as e:
            print(f"⚠️ 敏感词检查异常: {e}")
    


    session_lock = chat_service.get_session_lock(session_id)
    
    # 准备上下文
    with session_lock:
        session_data, record_id = chat_service.ensure_session_and_project(
            session_id, current_user_id
        )
        
        db_service.upsert_chat_turn(
            session_data, turn_id, prompt, selected_models=selected_models
        )

        db_service.append_thread_message(
            session_id, model_key, role="user", content=prompt, user_id=current_user_id
        )
        
        thread_messages = db_service.get_thread_history(
            session_id, model_key, user_id=current_user_id
        )
        # 这个函数控制模型的记忆能力
        thread_messages = chat_service.trim_thread(thread_messages, config.MAX_THREAD_MESSAGES)

        if not thread_messages or thread_messages[0].get("role") != "system":
            thread_messages.insert(0, {
                "role": "system",
                "content": config.SYSTEM_PROMPT
            })
    
    def generate():
        """
        流式生成大模型回复的生成器函数，支持API调用重试。
        -----------------------------------
        1. 首先 yield 一条 meta 信息，包含会话、模型等元数据。
        2. 调用 llm_service.call_llm_stream()，每次从模型获得新内容（字符/片段），就 yield 一条 delta 事件（包含内容和推理过程）。
        3. 若API调用失败，自动重试，重试次数由环境变量 LLM_STREAM_RETRY_MAX 控制（默认3次）。
        4. 所有重试失败后，yield 一条 error 事件。
        5. finally 块中会将已生成内容（无论是否完整）保存到数据库，包括 assistant 消息和历史记录。
        6. 该生成器被 Flask 的 Response(stream_with_context(...)) 包裹，实现 HTTP 流式返回，前端可边接收边渲染。
        
        返回格式：每行一个 JSON 字符串，事件类型如下：
            {"event": "meta", ...}      # 首行，元信息
            {"event": "delta", ...}     # 增量内容
            {"event": "done"}           # 结束
            {"event": "error", ...}     # 异常
        """
        full_content = ""
        full_reasoning = ""
        err = None
        retry_max = int(os.environ.get("LLM_STREAM_RETRY_MAX", 3))
        retry_base_delay = float(os.environ.get("LLM_STREAM_RETRY_BASE_DELAY", 1.0))  # 秒，默认1s
        attempt = 0
        yield json.dumps({
            "event": "meta",
            "session_id": session_id,
            "record_id": record_id,
            "turn_id": turn_id,
            "model_key": model_key,
            "model": model_name
        }, ensure_ascii=False) + "\n"
        while attempt < retry_max:
            attempt += 1
            full_content = ""
            full_reasoning = ""
            err = None
            try:
                for c_ch, r_ch in llm_service.call_llm_stream(
                    provider,
                    model_name,
                    thread_messages
                ):
                    # 防御性处理：确保增量为字符串，避免非JSON文本被直接写入流
                    try:
                        c_safe = c_ch or ""
                        r_safe = r_ch or ""
                        # 强制转为字符串以防出现非str类型
                        if not isinstance(c_safe, str):
                            c_safe = str(c_safe)
                        if not isinstance(r_safe, str):
                            r_safe = str(r_safe)

                        if c_safe:
                            full_content += c_safe
                        if r_safe:
                            full_reasoning += r_safe

                        payload = {"event": "delta", "delta": c_safe, "reasoning_delta": r_safe}
                        try:
                            yield json.dumps(payload, ensure_ascii=False) + "\n"
                        except Exception as je:
                            # 如果序列化失败，记录并发送 error 事件而不是裸文本
                            logging.getLogger("error").error("ndjson_serialize_failed", extra={"extra_fields": {"error": str(je), "payload": repr(payload)}})
                            yield json.dumps({"event": "error", "content": f"Stream serialization error: {str(je)}"}, ensure_ascii=False) + "\n"
                    except Exception as ee:
                        # 捕获任何意外，记录并通知前端，避免把原始异常文本混入流
                        logging.getLogger("error").error("stream_chunk_processing_failed", extra={"extra_fields": {"error": str(ee), "raw_chunk": repr((c_ch, r_ch))}}, exc_info=True)
                        yield json.dumps({"event": "error", "content": f"Stream processing error: {str(ee)}"}, ensure_ascii=False) + "\n"
                yield json.dumps({"event": "done"}, ensure_ascii=False) + "\n"
                break  # 成功则退出重试
            except GeneratorExit:
                raise
            except Exception as e:
                err = str(e)
                if attempt < retry_max:
                    # 重试中，通知前端
                    yield json.dumps({"event": "retry", "attempt": attempt, "max": retry_max, "error": err}, ensure_ascii=False) + "\n"
                    delay = retry_base_delay * (2 ** (attempt - 1))
                    time.sleep(delay)
        # 如果所有重试都失败，最后一次err不为None，需返回error事件
        if err:
            yield json.dumps({"event": "error", "content": f"[重试{attempt}/{retry_max}] {err}"}, ensure_ascii=False) + "\n"
        # finally 块
        display_content = chat_service.compose_display(full_reasoning, full_content)
        if err:
            display_content = (
                display_content + f"\n\n[请求失败] {err}"
            ) if display_content else f"[请求失败] {err}"
        chat_service.save_assistant_message(
            session_id, turn_id, model_key,
            full_content, display_content, current_user_id
        )
        chat_service.save_record_turn(
            record_id, turn_id, prompt, model_key, display_content,
            selected_models, current_user_id
        )
    
    resp = Response(stream_with_context(generate()), mimetype="application/x-ndjson")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


@chat_bp.route("/turn/order", methods=["POST"])
@login_required
def set_turn_order():
    """设置 turn 的模型顺序"""
    current_user_id = session.get('user_id')
    data = request.json or {}
    
    session_id = (data.get("session_id") or "").strip()
    turn_id = (data.get("turn_id") or "").strip()
    record_id = (data.get("record_id") or "").strip()
    model_order = data.get("model_order") or []
    
    if (not session_id and not record_id) or not turn_id or not isinstance(model_order, list):
        return jsonify({
            "status": "error",
            "content": "Missing (session_id or record_id) and turn_id/model_order"
        }), 400
    
    try:
        if session_id:
            db_service.set_turn_order(
                session_id, turn_id, model_order, user_id=current_user_id
            )
        if record_id:
            db_service.set_record_turn_order(
                record_id, turn_id, model_order, user_id=current_user_id
            )
    except Exception as e:
        return jsonify({"status": "error", "content": str(e)}), 400
    
    return jsonify({"status": "success"})


@chat_bp.route("/check-sensitive", methods=["POST"])
def check_sensitive():
    """检查文本是否包含敏感词（前端实时检查）"""
    if get_filter is None:
        # 敏感词模块未成功加载，返回不敏感（前端不显示提示）
        return jsonify({"status": "success", "is_sensitive": False, "word": None})
    
    data = request.json or {}
    text = (data.get("text") or "").strip()
    
    if not text:
        return jsonify({"status": "success", "is_sensitive": False, "word": None})
    
    try:
        sensitive_filter = get_filter()
        is_sensitive, sensitive_word, _ = sensitive_filter.detect(text)
        
        return jsonify({
            "status": "success",
            "is_sensitive": is_sensitive,
            "word": sensitive_word
        })
    except Exception as e:
        print(f"⚠️ 敏感词检查异常: {e}")
        return jsonify({"status": "success", "is_sensitive": False, "word": None})


@chat_bp.route("/chat/deep", methods=["POST"])
@login_required
def chat_deep():
    """
    聊天接口（流式）
    -------------------
    前端通过 POST /api/chat/deep 请求大模型流式输出（如逐字/逐句返回）。
    
    前端需传递参数：
        - session_id: 当前会话ID（字符串，必填）
        - turn_id: 本轮对话ID（字符串，必填）
        - prompt: 用户输入内容（字符串，必填）
        - provider: 大模型提供方（如 'gpt', 'gemini', 'silicon'，必填）
        - model: 具体模型名（如 'gpt-3.5-turbo'，必填）
        - model_key: 模型标识（如 'gpt'，必填）
        - selected_models: 选择的模型列表（数组，可选）
        - serial_index: 当前模型在本轮中的顺序编号（int，可选）
    
    处理流程：
        1. 校验参数，敏感词检查。
        2. 获取会话锁，确保 session/record 存在。
        3. 保存用户输入到数据库（turn、thread）。
        4. 获取上下文历史，插入系统提示词。
        5. 通过 llm_service.call_llm_deep() 调用大模型API，边生成边返回。
        6. 以 NDJSON 流式返回：meta（元信息）、delta（增量内容）、done、error 事件。
        7. 结束后保存大模型回复到数据库。
    
    返回：
        - mimetype: application/x-ndjson
        - 每行一个 JSON 事件：
            {"event": "meta", ...}  # 首行，包含模型/会话信息
            {"event": "delta", "delta": "新内容", "reasoning_delta": "推理内容"}
            {"event": "done"}        # 结束
            {"event": "error", "content": "错误信息"}  # 若有异常
    """
    current_user_id = session.get('user_id')
    data = request.json or {}

    session_id = (data.get("session_id") or "").strip()
    turn_id = (data.get("turn_id") or "").strip()
    prompt = (data.get("prompt") or "").strip()

    provider = (data.get("provider") or "").strip()
    model_name = (data.get("model") or "").strip()
    model_key = (data.get("model_key") or "").strip()

    # 模型顺序编号
    serial_index = data.get("serial_index", None)
    

    selected_models = data.get("selected_models") or []
    if not isinstance(selected_models, list):
        selected_models = []

    # 根据 serial_index 判断是否为第一个模型
    prev_model_output = None
    
    try:
        idx = int(serial_index) if serial_index is not None else None
    except Exception:
        idx = None

    if idx is not None and idx > 0 and idx <= len(selected_models):
        # 不是第一个模型，查找前一个模型的回答
        prev = selected_models[idx-1]
        if isinstance(prev, dict):
            prev_model_key = prev.get("key") or prev.get("provider")
        else:
            prev_model_key = prev
        if prev_model_key:
            thread_messages_prev = db_service.get_thread_history(
                session_id, prev_model_key, user_id=current_user_id
            )
            for msg in reversed(thread_messages_prev):
                if msg.get("role") == "assistant":
                    prev_model_output = msg.get("content")
                    break


    # 一系列验证
    # 参数验证
    if not session_id or not turn_id or not prompt:
        return jsonify({
            "status": "error",
            "content": "Missing session_id/turn_id/prompt"
        }), 400
    if provider not in {"gemini", "gpt", "silicon"}:
        return jsonify({"status": "error", "content": "Unknown provider"}), 400
    if not model_name or not model_key:
        return jsonify({"status": "error", "content": "Missing model/model_key"}), 400  
    # 敏感词检查
    if get_filter is not None:
        try:
            sensitive_filter = get_filter()
            is_sensitive, sensitive_word, _ = sensitive_filter.detect(prompt)
            if is_sensitive:
                return jsonify({
                    "status": "error",
                    "content": f"输入包含敏感词汇，已被拦截。请修改后重新提问。",
                    "sensitive_word": sensitive_word
                }), 403
        except Exception as e:
            print(f"⚠️ 敏感词检查异常: {e}")
    


    session_lock = chat_service.get_session_lock(session_id)
    
    # 准备上下文
    with session_lock:
        session_data, record_id = chat_service.ensure_session_and_project(
            session_id, current_user_id
        )
        
        db_service.upsert_chat_turn(
            session_data, turn_id, prompt, selected_models=selected_models
        )
        
        thread_messages = []
        thread_messages = db_service.get_thread_history(
            session_id, model_key, user_id=current_user_id
        )
        # 这个函数控制模型的记忆能力
        thread_messages = chat_service.trim_thread(thread_messages, config.MAX_THREAD_MESSAGES)

        initial_prompt = "请阅读以下问题{question}\n"
        summary = "针对:\"{question}\"，1、summary:先阅读并总结以下观点：{last_prompt}\n"
        analysis = "2、analysis：然后针对该观点进行反思和分析。"
        other_opinion = "还有一些现有观点包括：{pre_prompt}"



        thought = "3、opinion：提出与以上观点（包括总结的观点）都不同的思考，不能提到以上观点，不少于400字。有学术性的，逻辑严密且不失创造力地回答用户问题"
        scheme = "输出请严格遵循有效的JSON格式，严格遵循给定的JSON框架，将summary，analysis，opinion填入对应位置，输出格式为：{\"summary\":\"\",\"analysis\":\"\",\"opinion\":\"\"}，不要有多余的文字描述。"



        if serial_index == 0:
            thread_messages.append({
                "role": "user",
                "content": initial_prompt.format(question=prompt)
            })
        # elif serial_index == 1:
        #     thread_messages.append({
        #         "role": "user",
        #         "content":
        #             summary.format(
        #                 question=prompt,
        #                 last_prompt=json.loads(prev_model_output).get("opinion") or "",
        #             ) 
        #             + analysis 
        #             + thought 
        #             + scheme 
        #     })
        #     print(model_name+":")
        #     print(thread_messages)
        elif serial_index == len(selected_models):
            thread_messages.append({
                "role": "user",
                "content":
                    summary.format(
                        question=prompt,
                        last_prompt=json.loads(prev_model_output).get("opinion") or "",
                    ) 
                    + analysis 
                    + scheme
            })
        else:
            thread_messages.append({
                "role": "user",
                "content":
                    summary.format(
                        question=prompt,
                        last_prompt=json.loads(prev_model_output).get("opinion") or "",
                    ) 
                    + analysis 
                    # + other_opinion.format(
                    #     pre_prompt=json.loads(prev_model_output).get("summary")  or ""
                    # ) 
                    + thought 
                    + scheme
            })

        if serial_index < len(selected_models):

            db_service.append_thread_message(
                session_id, model_key, role="user", content=prompt, user_id=current_user_id
            )


        if not thread_messages or thread_messages[0].get("role") != "system":
            thread_messages.insert(0, {
                "role": "system",
                "content": config.SYSTEM_PROMPT
            })
    
    def generate(schema):
        """
        流式生成大模型回复的生成器函数，支持API调用重试。
        -----------------------------------
        1. 首先 yield 一条 meta 信息，包含会话、模型等元数据。
        2. 调用 llm_service.call_llm_stream()，每次从模型获得新内容（字符/片段），就 yield 一条 delta 事件（包含内容和推理过程）。
        3. 若API调用失败，自动重试，重试次数由环境变量 LLM_STREAM_RETRY_MAX 控制（默认3次）。
        4. 所有重试失败后，yield 一条 error 事件。
        5. finally 块中会将已生成内容（无论是否完整）保存到数据库，包括 assistant 消息和历史记录。
        6. 该生成器被 Flask 的 Response(stream_with_context(...)) 包裹，实现 HTTP 流式返回，前端可边接收边渲染。
        
        返回格式：每行一个 JSON 字符串，事件类型如下：
            {"event": "meta", ...}      # 首行，元信息
            {"event": "delta", ...}     # 增量内容
            {"event": "done"}           # 结束
            {"event": "error", ...}     # 异常
        """
        full_content = ""
        full_reasoning = ""
        err = None
        retry_max = int(os.environ.get("LLM_STREAM_RETRY_MAX", 3))
        retry_base_delay = float(os.environ.get("LLM_STREAM_RETRY_BASE_DELAY", 1.0))  # 秒，默认1s
        attempt = 0
        yield json.dumps({
            "event": "meta",
            "session_id": session_id,
            "record_id": record_id,
            "turn_id": turn_id,
            "model_key": model_key,
            "model": model_name
        }, ensure_ascii=False) + "\n"
        while attempt < retry_max:
            attempt += 1
            full_content = ""
            full_reasoning = ""
            err = None
            try:
                # 非流式 deep 调用（可重试）
                resp_obj = llm_service.call_llm_deep(provider, model_name, thread_messages, schema=schema)
                # 规范化为包含 summary/analysis/opinion 三键的字典，优先从 resp_obj、resp_obj['raw'] 或文本中抽取
                try:
                    resp_normal = _to_canonical_result(resp_obj)
                except Exception:
                    # 最后兜底，保证为三键字典
                    resp_normal = {"summary": "", "analysis": "", "opinion": ""}

                # 返回结构化 result 事件
                try:
                    yield json.dumps({"event": "result", "result": resp_normal}, ensure_ascii=False) + "\n"
                    yield json.dumps({"event": "done"}, ensure_ascii=False) + "\n"
                except Exception:
                    yield json.dumps({"event": "error", "content": "Result serialization failed"}, ensure_ascii=False) + "\n"

                # 为后续保存构建显示内容（使用规范化后的结构）
                try:
                    full_content = json.dumps(resp_normal, ensure_ascii=False)
                except Exception:
                    full_content = str(resp_normal)
                full_reasoning = ""
                # 已收到结构化结果，跳过后续流式拼接
                if resp_obj is not None:
                    break
                for c_ch, r_ch in llm_service.call_llm_stream(
                    provider, 
                    model_name, 
                    thread_messages
                ):
                    if c_ch:
                        full_content += c_ch
                    if r_ch:
                        full_reasoning += r_ch
                    yield json.dumps({
                        "event": "delta",
                        "delta": c_ch,
                        "reasoning_delta": r_ch
                    }, ensure_ascii=False) + "\n"
                yield json.dumps({"event": "done"}, ensure_ascii=False) + "\n"
                break  # 成功则退出重试
            except GeneratorExit:
                raise
            except Exception as e:
                err = str(e)
                if attempt < retry_max:
                    # 重试中，通知前端
                    yield json.dumps({"event": "retry", "attempt": attempt, "max": retry_max, "error": err}, ensure_ascii=False) + "\n"
                    delay = retry_base_delay * (2 ** (attempt - 1))
                    time.sleep(delay)
        # 如果所有重试都失败，最后一次err不为None，需返回error事件
        if err:
            yield json.dumps({"event": "error", "content": f"[重试{attempt}/{retry_max}] {err}"}, ensure_ascii=False) + "\n"
        display_content = chat_service.compose_display(full_reasoning, full_content)
        if err:
            display_content = (
                display_content + f"\n\n[请求失败] {err}"
            ) if display_content else f"[请求失败] {err}"
        
        if serial_index == len(selected_models):
            chat_service.save_assistant_message_(
                session_id, turn_id, model_key,
                full_content, display_content, current_user_id
            )
            chat_service.save_record_turn(
                record_id, turn_id, prompt, model_key, display_content,
                selected_models, current_user_id, isMessages_=True
            )
        else:
            chat_service.save_assistant_message(
                session_id, turn_id, model_key,
                full_content, display_content, current_user_id
            )
            chat_service.save_record_turn(
                record_id, turn_id, prompt, model_key, display_content,
                selected_models, current_user_id
            )
    

    if serial_index == 0:
        schema = AnswerInitial.model_json_schema()
    elif serial_index == len(selected_models):
        schema = AnswerEnd.model_json_schema()
    else:
        schema = AnswerTotal.model_json_schema()

    resp = Response(stream_with_context(generate(schema)), mimetype="application/x-ndjson")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    logging.getLogger("access").debug(f"prepared response for model={model_name}")
    return resp


def _try_parse_json_from_string(s: str):
    """尝试从任意字符串中解析 JSON，返回 dict 或 None。"""
    if not isinstance(s, str):
        return None
    txt = s.strip()
    try:
        return json.loads(txt)
    except Exception:
        pass

    # 剥离 Markdown 代码块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", txt)
    if m:
        cand = m.group(1).strip()
        try:
            return json.loads(cand)
        except Exception:
            pass

    # 查找第一个平衡的大括号子串
    start = txt.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(txt)):
            ch = txt[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    cand = txt[start:i+1]
                    try:
                        return json.loads(cand)
                    except Exception:
                        break

    # 宽松替换单引号为双引号再尝试
    try:
        cand2 = txt.replace("'", '"')
        return json.loads(cand2)
    except Exception:
        return None


def _to_canonical_result(obj) -> dict:
    """将任意 obj 规范为包含 summary/analysis/opinion 三键的字典（字符串值）。"""
    keys = ("summary", "analysis", "opinion")
    def ensure(d: dict):
        return {k: (d.get(k) if d.get(k) is not None else "") for k in keys}

    # 如果已经是 dict 且包含目标键，直接返回
    if isinstance(obj, dict):
        if any(k in obj for k in keys):
            return ensure(obj)
        # 优先处理 raw 字段
        if 'raw' in obj and isinstance(obj['raw'], str):
            text = obj['raw']
        else:
            try:
                text = json.dumps(obj, ensure_ascii=False)
            except Exception:
                text = str(obj)
    elif isinstance(obj, str):
        parsed = _try_parse_json_from_string(obj)
        if isinstance(parsed, dict) and any(k in parsed for k in keys):
            return ensure(parsed)
        text = obj
    else:
        text = str(obj)

    # 宽松抽取字段（兼容无引号的键）
    out = {}
    for k in keys:
        # 先尝试严格 JSON 解析
        parsed = _try_parse_json_from_string(text)
        if isinstance(parsed, dict) and k in parsed:
            out[k] = parsed.get(k) or ""
            continue

        # 宽松正则匹配 key : value 或 key = value
        pat = re.compile(rf'(?is){k}\s*[:=]\s*(?:"([\s\S]*?)"|\'([^\']*?)\'|([^\n,]+))')
        m = pat.search(text)
        if m:
            val = next((g for g in m.groups() if g), "")
            out[k] = val.strip()
        else:
            out[k] = ""

    return {k: (out.get(k) or "") for k in keys}

