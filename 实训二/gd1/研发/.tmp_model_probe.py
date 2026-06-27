from openai import OpenAI

client = OpenAI(api_key='sk-ecnifwexetdlrngddmlsarkhqwixtrzoccnstegdjtupaekf', base_url='https://api.siliconflow.cn/v1')
models = [
    'deepseek-ai/DeepSeek-V4-Flash',
    'deepseek-ai/DeepSeek-V4-Pro',
    'deepseek-ai/DeepSeek-V3.2',
    'deepseek-ai/DeepSeek-V3',
    'deepseek-ai/DeepSeek-R1',
]
for model in models:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': 'ping'}],
            max_tokens=1,
        )
        print(f'OK::{model}')
    except Exception as exc:
        print(f'ERR::{model}::{exc}')
