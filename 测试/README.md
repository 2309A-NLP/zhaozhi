# 测试目录说明

当前测试目录包含：

- `test_ragas.py`：RAGAS 评测脚本
- `ragas_cases.json`：默认评测样例

## 运行方式

先启动后端服务，再进入项目根目录执行：

```powershell
python 测试/test_ragas.py
```

常用参数示例：

```powershell
python 测试/test_ragas.py --base-url http://127.0.0.1:8000 --results-file 测试/ragas_result.json
```

```powershell
python 测试/test_ragas.py --username eval_user --password ChangeMe123 --knowledge-domains general,medical,legal,finance
```

## 脚本改进点

- 已适配当前项目的登录鉴权机制
- 支持登录失败后自动注册测试账号
- 支持通过 JSON 文件维护测试样例
- 支持通过命令行参数和环境变量覆盖默认配置
- 支持把评测结果导出为 JSON 文件
