import os
import json
import hashlib
from time import sleep
from openai import OpenAI
import requests
from urllib import parse

client = OpenAI(
    api_key= "your_token",
    base_url="LLM 域名"
)
your_model_name = "your_model_name" #模型名

def get_md5(string):
    md5 = hashlib.md5()
    md5.update(string.encode('utf-8'))
    return md5.hexdigest()

def llm_translate_text(query, from_lang='en', to_lang='zh', retries=10, delay=5, timeout=10):
    prompt = f"将以下文本从{from_lang}翻译为{to_lang}。保留备选参数列表的内容不变，保留(E.g.)的内容不变。文本：\n{query}"
    for attempt in range(retries):
        try:
            completion = client.chat.completions.create(
                model="your_model_name",
                messages=[{'role': 'system', 'content': '你是一个翻译机器人，你的任务是将英文翻译成中文。你只完成文本的翻译工作，不做任何的计算和推理。你答案第一行是你的翻译结果，不要包含任何额外的信息。'},
                          {'role': 'user', 'content': prompt}],
                stream=False,
                max_tokens=512,
                temperature=0,
                timeout=timeout,
            )
            result = completion.model_dump_json()
            translated_text = json.loads(result)["choices"][0]["message"]["content"]
            return translated_text.split('\n')[0]
        except Exception as e:
            print(f"请求失败：{str(e)}，重试 {attempt + 1}/{retries}")
            print(prompt)
            sleep(delay)
    return "请求失败，请稍后重试。"

def process_all_fields(data):
    if isinstance(data, dict):
        for key in list(data.keys()):
            value = data[key]
            if key in ['description', 'content'] and isinstance(value, str):
                data[key] = llm_translate_text(value)
            else:
                process_all_fields(value)
    elif isinstance(data, list):
        for item in data:
            process_all_fields(item)
    return data


def translate_file(file_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    output_name = os.path.basename(file_path).replace('BFCL_v3_', 'BFCL_v3_')
    output_path = os.path.join(output_dir, output_name)

    with open(file_path, 'r', encoding='utf-8') as fin, \
            open(output_path, 'w', encoding='utf-8') as fout:

        for line in fin:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                process_all_fields(data)
                fout.write(json.dumps(data, ensure_ascii=False) + '\n')
            except json.JSONDecodeError as e:
                print(f"JSON解析错误（{file_path}）：{str(e)}")
                continue

    print(f"文件已保存：{output_path}")


def main():
    input_dir = '../data'
    output_dir = '../data'
    done_list = []
    todo_list = []

    # 查找所有BFCL_v3_开头的json文件
    for filename in os.listdir(input_dir):
        if (filename.startswith('BFCL_v3_')
                and filename.endswith('.json')
                and filename not in done_list
                and filename in todo_list
        ):

            file_path = os.path.join(input_dir, filename)
            print(f"正在处理文件：{filename}")
            try:
                translate_file(file_path, output_dir)
            except Exception as e:
                print(f"处理文件 {filename} 时出错：{str(e)}")


if __name__ == '__main__':
    main()
