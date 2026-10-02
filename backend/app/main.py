from fastapi import FastAPI
from pydantic import BaseModel
from typing import Literal

app = FastAPI(title='Punjab Education Intelligence Platform API', version='0.1.0')

class GenerateRequest(BaseModel):
    curriculum: str
    subject: str
    book: str
    chapter: str
    topic: str
    question_type: Literal['mcq','subjective','quiz','assignment']
    count: int = 10
    difficulty: Literal['easy','medium','hard'] = 'medium'
    language: Literal['en','ur'] = 'en'

@app.get('/health')
def health(): return {'status':'ok'}

@app.get('/api/curriculum')
def curriculum():
    return {'curricula':[{'id':'punjab-2025','name':'Punjab Curriculum','grades':['9','10','11','12']}]} 

@app.post('/api/ai/generate')
def generate(req: GenerateRequest):
    # First-cut contract. Connect this endpoint to the chosen LLM/RAG service next.
    return {'status':'queued','request':req.model_dump(),'items':[],'message':'AI provider integration pending.'}
