from fastapi import APIRouter, Depends
from app.services.hackathon2025 import excute_test_gen,doc_to_markdown_string
import psutil
import time

router = APIRouter()

@router.get("/gentestcases")
async def hack_check():
    testcases = excute_test_gen()
    if testcases:
         return {
            "code": 200,
            "msg": "gen cases success",
            "data": testcases
         }
    else:
         return {
            "code": 404,
            "message": "gen cases fail",
         }
    
@router.get("/docxtomarkdown")
async def docx_to_markdown():
    dpcx_path = "E://RunTestZK//tests//AI测试材料准备//2025hackathon//material//11111.docx"
    testcases = doc_to_markdown_string(dpcx_path)
    if testcases:
         return {
            "code": 200,
            "msg": "gen cases success",
            "data": testcases
         }
    else:
         return {
            "code": 404,
            "message": "gen cases fail",
         }