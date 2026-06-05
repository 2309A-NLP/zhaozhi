# 概要设计

## 子系统交互
- 前端通过 `HTTP + JSON` 调用接口层
- 接口层只做入参校验和响应封装
- 业务层负责查询编排、提示词组装、答案生成
- 数据层负责 Mysql / Milvus / Redis 访问
- 模型层负责大模型 API 和 Embedding API

## 在线链路
`前端 -> 接口层 -> 业务层 -> 数据层/模型层 -> 返回 JSON`

## 离线链路
`PDF -> 解析 -> 切分 -> 向量化 -> Mysql/Milvus/Redis 入库`

