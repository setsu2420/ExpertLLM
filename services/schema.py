from pydantic import BaseModel, Field
from typing import List, Optional

class AnswerTotal(BaseModel):
   summary: str = Field(description="观点的总结")
   analysis: str = Field(description="观点的反思与分析，可能包括观点的优势和不足，以及可能的改进方向。")
   opinion: str = Field(description="与其它现有观点都不同的自己的思考。")


class AnswerInitial(BaseModel):
   opinion: str


class AnswerEnd(BaseModel):
   summary: str = Field(description="观点的总结")
   analysis: str = Field(description="观点的反思与分析，可能包括观点的优势和不足，以及可能的改进方向。")
   

# class Answer(BaseModel):
#    summery: str = Field(description="")
#    analysis: str = Field(description="Quantity of the ingredient, including units.")
#    opinion: str = Field(description="Optional notes about the ingredient.")


# class Recipe(BaseModel):
#     recipe_suname: str = Field(description="The name of the recipe.")
#     prep_time_minutes: Optional[int] = Field(description="Optional time in minutes to prepare the recipe.")
#     ingredients: List[Ingredient]
#     instructions: List[str]