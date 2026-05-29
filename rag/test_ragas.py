"""本脚本用于调用接口并评估 RAG 回答质量。"""  # 说明脚本用途：构造测试集并使用 RAGAS 计算评测指标。
import os  # 导入环境变量模块，用来读取接口基础地址配置。

import requests  # 导入 HTTP 请求库，用来调用本地聊天接口。
from datasets import Dataset  # 导入 Hugging Face Dataset，用来组织评测样本。
from ragas import evaluate  # 导入 RAGAS 评测入口函数，用来计算各项指标。
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness  # 导入评测指标：答案相关性、上下文精确率、召回率和忠实度。


BASE_URL = os.getenv("RAG_API_BASE", "http://localhost:8000")  # 读取接口基础地址；RAG_API_BASE 是环境变量名，默认值指向本机 8000 端口。


def prepare_test_dataset():  # 定义数据准备函数，用来请求接口并整理 RAGAS 所需数据集。
    test_questions = [  # 定义测试问题列表，作为发给聊天接口的输入样本。
        "高血压患者应该注意哪些饮食习惯？",  # 医疗领域测试问题，用来验证健康知识检索与回答。
        "民法典中关于合同违约的常见责任有哪些？",  # 法律领域测试问题，用来验证法律知识回答。
        "股票投资有哪些常见的风险控制策略？",  # 金融领域测试问题，用来验证投资风险类回答。
    ]  # 结束测试问题列表定义。
    test_answers = [  # 定义参考答案列表，作为 RAGAS 的 ground truth 对照答案。
        "通常包括控制盐摄入、减少高脂食物、均衡饮食并结合医生建议管理血压。",  # 对应第一个医疗问题的参考答案。
        "常见责任包括继续履行、采取补救措施、赔偿损失、支付违约金等。",  # 对应第二个法律问题的参考答案。
        "常见策略包括分散投资、设置止损、控制仓位、定期复盘和避免情绪化交易。",  # 对应第三个金融问题的参考答案。
    ]  # 结束参考答案列表定义。

    contexts = []  # 初始化上下文列表，用来存储每次回答附带的检索片段。
    responses = []  # 初始化回答列表，用来存储接口返回的最终答案。

    for question in test_questions:  # 依次遍历每一个测试问题并调用接口。
        resp = requests.post(  # 发送 POST 请求到聊天接口，拿到模型回复和检索结果。
            f"{BASE_URL}/api/chat/",  # 请求地址由基础地址和聊天接口路径拼接得到。
            json={"user_id": 1, "role_id": 0, "message": question},  # json 参数是请求体：user_id 指用户，role_id 指角色，message 是当前问题。
            timeout=120,  # timeout=120 表示最多等待 120 秒，防止请求无限阻塞。
        )  # 结束本次 requests.post 调用。
        resp.raise_for_status()  # 若接口返回 4xx 或 5xx 状态码则抛出异常，避免静默失败。
        data = resp.json()  # 把接口响应解析为字典，便于后续读取字段。
        responses.append(data["response"])  # 记录接口返回的最终回答文本。
        contexts.append([doc["text"] for doc in data.get("retrieved_docs", [])])  # 提取每个检索文档的 text 字段，作为评测使用的上下文列表。

    return Dataset.from_dict(  # 把问题、回答、上下文和参考答案组装成 RAGAS 可识别的数据集对象。
        {  # 构造数据集字段字典，键名需要符合 RAGAS 约定。
            "question": test_questions,  # question 字段保存提问列表。
            "answer": responses,  # answer 字段保存模型实际回答。
            "contexts": contexts,  # contexts 字段保存每个问题对应的检索上下文。
            "ground_truth": test_answers,  # ground_truth 字段保存人工参考答案。
        }  # 结束数据集字段字典定义。
    )  # 返回构造好的 Dataset 实例。


def run_ragas_evaluation():  # 定义评测入口函数，用来执行数据准备、评分和结果输出。
    dataset = prepare_test_dataset()  # 先准备评测所需的数据集。
    result = evaluate(  # 调用 RAGAS evaluate 函数，对数据集进行多指标评分。
        dataset,  # 第一个参数是待评测的数据集对象。
        metrics=[context_precision, context_recall, faithfulness, answer_relevancy],  # metrics 参数指定要计算的指标列表。
    )  # 结束本次 evaluate 调用。
    print("=" * 50)  # 打印分隔线，方便终端中查看结果区域。
    print("RAGAS 评测结果")  # 输出标题，标记下面是评测指标结果。
    print("=" * 50)  # 再打印一条分隔线，使输出更清晰。
    print(f"Context Precision: {result['context_precision'].mean():.4f}")  # 输出上下文精确率均值，衡量检索内容的相关程度。
    print(f"Context Recall: {result['context_recall'].mean():.4f}")  # 输出上下文召回率均值，衡量是否找回了足够多的相关内容。
    print(f"Faithfulness: {result['faithfulness'].mean():.4f}")  # 输出忠实度均值，衡量回答是否忠于检索上下文。
    print(f"Answer Relevancy: {result['answer_relevancy'].mean():.4f}")  # 输出答案相关性均值，衡量回答与问题是否匹配。
    return result  # 返回完整评测结果对象，便于调用方继续处理。


if __name__ == "__main__":  # 只有在直接运行当前脚本时才执行评测入口。
    run_ragas_evaluation()  # 调用评测函数开始执行整套评测流程。
