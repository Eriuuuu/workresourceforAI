import pypandoc
import requests
import json
import urllib3
import sseclient
import os
import time
from random import choice
from hashlib import md5
from string import digits,ascii_letters
import re

class testcases_gen():
   

    def test111(self):
        print("111111")
        return True
    
def doc_to_markdown_string(doc_path):
    """
    将doc/docx文件转换为markdown字符串
    """
    try:
        # 使用pandoc进行转换
        output = pypandoc.convert_file(doc_path, 'md', format='docx')
        return output
    except Exception as e:
        return f"转换出错: {str(e)}"

###############使用key和secret生成token###############
def generate_token(api_key, api_secret, url="https://copilot.glodon.com/api/auth/v1/access-token"):
    """
    生成token
    
    :param api_key: 租户的API Key，必填项
    :param api_secret: 租户的API Secret，必填项
    :param url: 请求的接口地址, 默认为内网url
    :returns: 返回token
    """
    if api_key == "" or api_secret == "":
        print("请输入api_key和api_secret")
        return ""
    
    nowtime = time.time()
    timestamp = str(int(nowtime * 1000))
    noncestr = generate_random_str(24)
    raw_token = api_key + ":" + timestamp + ":" + noncestr + ":" + api_secret
    auth = generate_md5(raw_token)
    payload = {}
    headers = {
    'X-AIOT-APIKEY': api_key,
    'X-AIOT-TIMESTAMP': timestamp,
    'X-AIOT-NONCESTR': noncestr,
    'Authorization': "Basic " + auth
    }
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code == 200:
            res = response.json()
            if res["code"] != 200:
                raise Exception(res["message"])

            token ="Bearer " + res["data"]["accessToken"]
            return (token)
        else:
            raise Exception(response.status_code)
    except Exception as err:
        print('An exception happened: ' + str(err))
        return ""

def generate_md5(src):
    m = md5(src.encode(encoding='utf-8'))
    return m.hexdigest()

def generate_random_str(randomlength=24):
    str_list = [choice(digits + ascii_letters) for i in range(randomlength)]
    random_str = ''.join(str_list)
    return random_str


###############上传文件并获得URL###############
def upload_files(basetoken, uploadurl,filepath):
    with open(filepath, "rb") as f:
        files = {"file": f}
        data  = {"purpose": "infer"}
        headers = {"Authorization": basetoken}
        response = requests.post(uploadurl, files=files, data=data, headers=headers)
    if response.status_code == 200:
        res = response.json()
        if res["code"] != 200:
            raise Exception(res["message"])

        file_url= res["data"]["url"]
        print(file_url)
        return file_url
    else:
        raise Exception(response.status_code)


###############同步调用workflow###############
def workflow_apply(querystr,fileurl,workflow_URL, workflowtoken):
    payload ={
        "query": str(querystr),
        "fileUrls": [str(fileurl)]
    }

    header ={
        "Content-Type": "application/json",
        "Authorization": str(workflowtoken)
    }
    response = requests.post(workflow_URL,data=json.dumps(payload),headers=header)
    print(str(response))
    if response.status_code == 200:
        res = response.json()
        print(str(res))
        if res["code"] != 200:
            raise Exception(res["message"])

        output = res["data"].get("output", "N/A")
        output1 = res["data"].get("output1", "N/A") 
        output2 = res["data"].get("output2", "N/A")
        print("------------用例-----------------")
        print(output)
        print("--------------分堆情况-----------------")
        print(output2)
        print("-----------------end---------------")
        return True
    else:
        raise Exception(response.status_code)

###############异步调用workflow###############

def get_result(pid, auth):
    query_url = "https://copilot.glodon.com/api/cvforce/workflow/v1/process"
    header = {"Authorization": auth}
    res = requests.get(f"{query_url}/{pid}", headers=header)
    return res

def get_node_result(pid, node_id, auth):
    query_url = "https://copilot.glodon.com/api/cvforce/workflow/v1/process"
    header = {"Authorization": auth}
    res = requests.get(f"{query_url}/{pid}/node/{node_id}", headers=header)
    return res

def workflow_apply_async_requirementsgen(requirement_string,api_string,workflow_URL, workflowtoken):
    payload ={
        "requirement_string": str(requirement_string),
        "api_string": [str(api_string)]
    }

    header ={
        "Content-Type": "application/json",
        "Authorization": str(workflowtoken),
        "Async": "on"
    }
    response = requests.post(workflow_URL,data=json.dumps(payload),headers=header)
    return response


def workflow_apply_async_testcasesgen(cases: dict ,requirementdoc: str, modulename: str, workflow_URL: str, workflowtoken: str):
    payload ={
        "requirement_cases": cases,
        "requirement_doc": requirementdoc,
        "module_name": modulename,
    }

    header ={
        "Content-Type": "application/json",
        "Authorization": str(workflowtoken),
        "Async": "on"
    }
    response = requests.post(workflow_URL,data=json.dumps(payload),headers=header)
    return response

def get_end_node_id(base_token : str,processid:str, timeperiod: int = 1000 ,interval :int = 5):
    end_node_id= ''
    for i in range(timeperiod):
        response = get_result(processid, base_token)
        
        if response.status_code != 200:
            print("获取工作流过程状态失败：", response.status_code, response.text)
            break

        res = response.json()
        print(res)
        data = res.get("data") or {}

        if data.get("status") == "SUCCESS":
            end_node_id = res["data"]["results"][-1].get("nodeId")
            return end_node_id
        elif data.get("status") == "FAILED":
            end_node_id = res["data"]["results"][-1].get("nodeId")
            return end_node_id
        time.sleep(interval)
    return None


def clean_and_parse_json(raw_text):
    match = re.search(r'\[.*\]', raw_text, flags=re.S)
    if match:
        json_str = match.group()
        print(json_str)
        data = json.loads(json_str)
        # print(json.dumps(data, ensure_ascii=False, indent=2))
        return data
    else:
        print("未找到 JSON 段落")
        return None


def get_llm_result(response):
    
    if response.status_code != 200:
        print("url返回结果失败：", response.status_code, response.text)
        return None
    res = response.json()
    print("11111111111111111")
    print(res)
    result1 = res["data"].get("result", "N/A").get("outputs", "N/A").get("output", "N/A")
    print("22222222222222222222")
    print(result1)
    test_cases = clean_and_parse_json(result1)
    result2 = res["data"].get("result", "N/A").get("outputs", "N/A").get("output1", "N/A")
    print("3333333333333333")
    print(result2)
    test_cases2 = clean_and_parse_json(result2)
    result1 = res["data"].get("result", "N/A").get("outputs", "N/A").get("output", "N/A")
    print("4444444444444444444")
    print(result1)
    test_cases = clean_and_parse_json(result1)
    



###############调用对话型应用###############
#创建对话，获取sessionid
def create_session(host,app_id,token):
    payload ={
        "name": "测试会话",
        "finialMessage": "你好",
        "origin": "python-sdk",
        "netOpen": 1,
        "enableNetOpen": 2,
        "type": "" 
    }

    header ={
        "Content-Type": "application/json",
        "Authorization": f"{token}"
    }
    create_session_url=f"{host}/api/cvforce/data/v1/application/{app_id}/sessions"
    response = requests.post(create_session_url,data=json.dumps(payload),headers=header)
    if response.status_code == 200:
        res = response.json()
        if res["code"] != 200:
            raise Exception(res["message"])

        sessionid = res["data"]["id"]
        print(sessionid)
        return (sessionid)
    else:
        raise Exception(response.status_code)
    


def open_stream(url, data, token):
    """获取流式响应"""
    headers = {'Accept': 'text/event-stream'}
    if token:
        headers['Authorization'] = token
    headers['Content-Type'] = 'application/json'
    
    http = urllib3.PoolManager()
    json_data = json.dumps(data)
    return http.request('POST', url, preload_content=False, headers=headers, body=json_data)


def stream_chat(API_URL,APP_ID,SESSION_ID,content,token):
    """流式聊天函数"""
    url = f"{API_URL}?applicationId={APP_ID}&sessionId={SESSION_ID}"
    
    jsondata = {
        "chatMode": 0,
        "content": content,
        "stream": True
    }
    
    print(f"用户: {content}")
    print("AI: ")
    
    try:
        response = open_stream(url, jsondata, token)
        client = sseclient.SSEClient(response)
        stream = client.events()
        
        while True:
            try:
                event = next(stream)
                data = event.data
                print(data)
            except StopIteration:
                print("end")
                break
                
    except Exception as e:
        print(f"错误: {e}")

#万能取值器,
def safe_get(obj, *keys, default=None):
    """
    万能取值：
      - 遇到 dict 用 .get
      - 遇到 list 就用索引 0，再递归
    """
    for k in keys:
        if isinstance(obj, list) and obj:
            obj = obj[0]
        if isinstance(obj, dict):
            obj = obj.get(k, default)
        else:
            return default
    return obj


def stream_chat2(api_base: str, app_id: str, session_id: str, content: str, token: str):
    """
    流式对话，自动输出 AI 回复，直到结束
    """
    url = f"{api_base}?applicationId={app_id}&sessionId={session_id}"
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}" if not token.startswith("Bearer") else token
    }
    payload = {"chatMode": 0, "content": content, "stream": True}

    resp = requests.post(url, json=payload, headers=headers, stream=True)
    resp.raise_for_status()

    client = sseclient.SSEClient(resp)
    print(f"用户: {content}\nAI: ", end="", flush=True)

    printed_reasoning_header = False
    printed_text_header = False
    for event in client.events():
        if event.data.strip() == "[DONE]":
            break
        try:
            chunk = json.loads(event.data)
            choices = safe_get(chunk, "data", "payload", "choices", default=[])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            text = delta.get("content", "")
            reasoning = delta.get("reasoningContent", "")
            # 打印（可按需换行）
            if text:
                if not printed_text_header:
                    print("[----------正文----------]\n", end="", flush=True)
                    printed_text_header = True
                print(text, end="", flush=True)
            if reasoning:
                if not printed_reasoning_header:
                    print("[----------思考链----------]\n", end="", flush=True)
                    printed_reasoning_header = True
                print(reasoning, end="", flush=True)
        except json.JSONDecodeError:
            pass
    print("\nend")




def excute_test_gen():
    #文本处理
    api_docx_path= "E://RunTestZK//tests//AI测试材料准备//2025hackathon//material//获取当前登录人有权限的指定组织的子节点.docx"
    requirement_docx_path ="E://RunTestZK//tests//AI测试材料准备//2025hackathon//material//获取当前登录人有权限的指定组织的子节点_需求.docx"
    api_markdown_string = doc_to_markdown_string(api_docx_path)
    requirements_markdown_string = doc_to_markdown_string(requirement_docx_path)

    ##生成token
    api_key = "hxHkv8BS0a1MDlsL"
    api_secret = "1X51L2RULJuTGyY0x18uss1p"
    host="https://copilot.glodon.com"
    get_token_api="/api/auth/v1/access-token"
    get_token_url = host+get_token_api
    base_token = generate_token(api_key, api_secret, get_token_url)

    ##异步调用工作流-需求点生成
    workflow_id ="ff1d44be-c7a3-400b-bfbb-833cbee1a469"
    workflow_URL = f"https://copilot.glodon.com/api/cvforce/workflow/v1/flowApi/{workflow_id}/process"
    
    response = workflow_apply_async_requirementsgen(requirements_markdown_string, api_markdown_string,workflow_URL, base_token) 
    pid = response.json().get("data", "")
    end_nodeod = get_end_node_id(base_token,pid,1000,10)
    print(end_nodeod)
    output_flowone =[]
    if end_nodeod.startswith("End"):
        response_of_flowone = get_node_result(pid, end_nodeod, base_token)
        response_data= response_of_flowone.json()

        print("-----------------需求点分堆-----------------------")
        output_data_requirementcases = response_data['data']['result']['data']['outputs']['output']
        requirement_stacks = clean_and_parse_json(output_data_requirementcases)
        output_flowone.append(requirement_stacks)

        print("-----------------需求文档-----------------------")
        output_data_requirement = response_data['data']['result']['data']['outputs']['output2']
        output_flowone.append(output_data_requirement)
        with open("output_requirement_stacks.json", "w", encoding="utf-8") as f:
            json.dump(requirement_stacks, f, ensure_ascii=False, indent=4)
    else:
        print("工作流运行失败")
        response_flowone_warning = get_node_result(pid, end_nodeod, base_token)
        response_data= response_flowone_warning.json()
        print(json.dumps(response_flowone_warning.json(), indent=2, ensure_ascii=False))

    ##异步调用工作流-测试点生成
    if len(output_flowone)!=0:
        tastcasesgen_workflowid = "14d28af1-3e44-467d-a9b2-9c7f3446025f"
        tastcasesgen_url = f"https://copilot.glodon.com/api/cvforce/workflow/v1/flowApi/{tastcasesgen_workflowid}/process"
        case_results = []
        countnum = 0
        stacks =output_flowone[0]
        for stack in stacks:
            for case in stack["requirements"]:
                testcasesgen_response = workflow_apply_async_testcasesgen(case,str(output_data_requirement),stack["module"],tastcasesgen_url,base_token)
                testcasesgen_pid = testcasesgen_response.json().get("data", "")
                testcasesgen_end_nodeod = get_end_node_id(base_token,testcasesgen_pid,1000,10)
                if testcasesgen_end_nodeod.startswith("End"):
                    testcasesgen_response2 = get_node_result(testcasesgen_pid, testcasesgen_end_nodeod, base_token)
                    testcase_data = testcasesgen_response2.json()
                    testcase_cases = testcase_data['data']['result']['data']['outputs']['testcases']
                    countnum +=1
                    print(f"-----------------{countnum}-----------------------")
                    testcase_cases_list = clean_and_parse_json(testcase_cases)                 
                    case_results.extend(testcase_cases_list)
        
        with open("output_testcase_1.json", "w", encoding="utf-8") as f:
            json.dump(case_results, f, ensure_ascii=False, indent=4)
        return case_results
    return False



