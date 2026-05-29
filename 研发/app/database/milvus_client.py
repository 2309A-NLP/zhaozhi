"""本模块用于封装 Milvus 连接、写入与混合检索逻辑。"""  # 说明当前模块或代码块的用途。
from __future__ import annotations  # 从 __future__ 中导入所需对象。
# 改变 Python 对注解（annotations）的求值策略：将原本在定义时立即求值的注解表达式，
# 改为以字符串形式延迟存储，在需要时才通过 typing.get_type_hints() 或类似机制求值。

import math  # 导入所需的模块或对象：math。
import threading  # 导入所需的模块或对象：threading。
from typing import Dict, List, Optional  # 从 typing 中导入所需对象。

try:  # 开始尝试执行可能出错的代码。
    from pymilvus import (  # 尝试导入 pymilvus 提供的检索、集合和连接相关对象。
        AnnSearchRequest,  # AnnSearchRequest 用来构造向量检索请求。
        Collection,  # Collection 表示 Milvus 中的集合对象。
        CollectionSchema,  # CollectionSchema 用来定义集合字段结构。
        DataType,  # DataType 枚举用于声明各字段的数据类型。
        FieldSchema,  # FieldSchema 用来定义单个字段的名称和属性。
        RRFRanker,  # RRFRanker 用来执行稠密检索与稀疏检索的融合排序。
        connections,  # connections 模块负责建立和管理 Milvus 连接。
        utility,  # utility 模块提供集合存在性等辅助能力。
    )  # 结束 pymilvus 导入列表。
except Exception:  # 捕获并处理前面代码抛出的异常。
    AnnSearchRequest = Collection = CollectionSchema = DataType = FieldSchema = RRFRanker = None  # 设置 AnnSearchRequest 的值，供后续逻辑使用。
    connections = utility = None  # 设置 connections 的值，供后续逻辑使用。

from ..config import config  # 从 ..config 中导入所需对象。


def _cosine_similarity(left: List[float], right: List[float]) -> float:
    """处理_cosine_similarity相关逻辑。

    参数：
        left: 比较或计算时使用的左侧值。
        right: 比较或计算时使用的右侧值。

    """
    if not left or not right:  # 判断left和right是否为空列表，只要有一个是空列表
        return 0.0  # 返回0.0
    size = min(len(left), len(right))  # 取left或right的最小长度
    numerator = sum(left[i] * right[i] for i in range(size))  # 调用size个元素，计算点积
    left_norm = math.sqrt(sum(value * value for value in left[:size]))  # 计算 left这个序列中前 size 个元素构成的向量的 长度（欧几里得范数）。
    right_norm = math.sqrt(sum(value * value for value in right[:size]))  # 计算 right 这个序列中前 size 个元素构成的向量的 长度（欧几里得范数）。
    if left_norm == 0 or right_norm == 0:
        return 0.0  # 这段代码是一个防御性编程措施：若零向量出现，直接返回 0.0 以避免除零错误，并表明没有相似性。直接返回 0.0 就是为了防止程序因“除零错误”（ZeroDivisionError）而崩溃

    return numerator / (left_norm * right_norm)  # 用两个向量的点积除以它们长度的乘积，得到一个只与方向有关、范围在 [-1,1] 的相似度分数。余弦相似度


def _sparse_score(query_sparse: Dict[int, float], doc_sparse: Dict[int, float]) -> float:  # 定义函数 _sparse_score，用于封装可复用的逻辑。
    """ 稀疏向量的点积

    参数：
        query_sparse: 用于检索的稀疏查询向量。
        doc_sparse: 当前函数使用的输入参数。
    """
    if not query_sparse or not doc_sparse:
        return 0.0
    return sum(query_sparse.get(key, 0.0) * value for key, value in doc_sparse.items())  # 标量分数


class MilvusClient:  # 定义类 MilvusClient，用于组织相关数据和行为。
    _memory_store: List[Dict] = []  # 执行这一行代码，完成当前逻辑。
    _id_counter = 1  # 设置 _id_counter 的值，供后续逻辑使用。
    _lock = threading.Lock()  # 调用 threading.Lock 并把结果保存到 _lock 中。

    def __init__(self, host: str, port: int, collection_name: Optional[str] = None):  # 定义函数 __init__，用于封装可复用的逻辑。
        """初始化对象，准备后续逻辑所需的依赖。

        参数：
            host: 当前函数使用的主机地址。
            port: 当前函数使用的网络端口。
            collection_name: 当前函数使用的输入参数。
        """
        self.host = host  # 设置 self.host 的值，供后续逻辑使用。
        self.port = port  # 设置 self.port 的值，供后续逻辑使用。
        self.collection_name = collection_name or config.MILVUS_COLLECTION_NAME  # 设置 self.collection_name 的值，供后续逻辑使用。
        self._use_memory = True  # 使用内存存储模式

        if connections and utility:  # 根据条件决定是否执行下面的代码块。
            try:  # 开始尝试执行可能出错的代码。
                self._connect()  # 调用 self._connect 处理当前这一步逻辑。
                self._ensure_collection(dim=config.EMBEDDING_DIM)  # 调用 self._ensure_collection 处理当前这一步逻辑。
                self._use_memory = False  # 表示已成功连接到真实的 Milvus 服务，所有操作将转发给真正的 Milvus 实例。
            except Exception:  # 捕获并处理前面代码抛出的异常。
                self._use_memory = True  # 设置 self._use_memory 的值，供后续逻辑使用。

    def _connect(self):  # 定义函数 _connect，用于封装可复用的逻辑。
        """处理_connect相关逻辑。
        """
        connections.connect(alias="default", host=self.host, port=self.port)  # 调用 connections.connect 处理当前这一步逻辑。

    def _ensure_collection(self, dim: int = 1024):  # 定义函数 _ensure_collection，用于封装可复用的逻辑。
        """处理_ensure_collection相关逻辑。

        参数：
            dim: 当前函数使用的输入参数。
        """
        if utility.has_collection(self.collection_name):  # 根据条件决定是否执行下面的代码块。
            collection = Collection(self.collection_name)  # 调用 Collection 并把结果保存到 collection 中。
            collection.load()  # 调用 collection.load 处理当前这一步逻辑。
            return collection  # 返回当前函数计算出的结果。

        fields = [  # 设置 fields 的值，供后续逻辑使用。
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),  # 调用 FieldSchema 处理当前这一步逻辑。
            FieldSchema(name="doc_id", dtype=DataType.INT64),  # 调用 FieldSchema 处理当前这一步逻辑。
            FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=65535),  # 调用 FieldSchema 处理当前这一步逻辑。
            FieldSchema(name="knowledge_domain", dtype=DataType.VARCHAR, max_length=100),  # 调用 FieldSchema 处理当前这一步逻辑。
            FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=dim),  # 调用 FieldSchema 处理当前这一步逻辑。
            # FLOAT_VECTOR (稠密向量): 它是全维度的32位单精度浮点数列表，每个维度都有值，固定长度。它的信息密度高，非常适合表达语义本质，
            # 但存储开销和计算成本也相对较大。主要用在语义相似度搜索 (如RAG)。
            FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),  # 调用 FieldSchema 处理当前这一步逻辑。
            # SPARSE_FLOAT_VECTOR (稀疏向量): 它绝大部分元素为0，只存储非零元素的索引和值 (e.g., {15: 2.1, 1024: 0.9})。
            # 因此，它极其节省存储和计算资源，非常适合处理超高维但稀疏的数据，如关键词匹配、词频统计。在构造上无需指定维度 (dim)，
            # 维度由实际存储的非零元素隐式决定。
        ]  # 结束当前列表、字典、元组、调用或代码块。
        schema = CollectionSchema(fields, description="RAG knowledge collection")  # 调用 CollectionSchema 并把结果保存到 schema 中。
        collection = Collection(self.collection_name, schema=schema)  # 调用 Collection 并把结果保存到 collection 中。
        collection.create_index(  # 开始调用 collection.create_index，后面继续传入参数。
            "dense_vector",  # 提供当前逻辑要使用的字符串内容。
            {"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}},  # 执行这一行代码，完成当前逻辑。
            # HNSW（Hierarchical Navigable Small World，分层可导航小世界）是当前最主流的近似最近邻（ANN）搜索算法之一，是高效向量检索的核心技术。
            # 它本质上是利用一种多层次的图结构来组织数据，以实现近似最近邻搜索（ANN），牺牲可接受的微小精度来换取巨大的速度提升。
            # 这种算法已成为许多高性能向量数据库（如 Milvus）的默认索引
        )  # 结束当前列表、字典、元组、调用或代码块。
        collection.create_index(  # 开始调用 collection.create_index，后面继续传入参数。
            "sparse_vector",  # 提供当前逻辑要使用的字符串内容。
            {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "IP"},  # 执行这一行代码，完成当前逻辑。
        )  # 结束当前列表、字典、元组、调用或代码块。
        collection.load()  # 调用 collection.load 处理当前这一步逻辑。
        return collection  # 返回当前函数计算出的结果。

    def hybrid_search(  #
        self,  #
        query_dense: List[float], # 查询的稠密向量
        query_sparse: Dict[int, float],  # 查询的稀疏向量
        domains: Optional[List[str]] = None,  # 限定知识列表
        doc_ids: Optional[List[int]] = None,  # 限定文档ID列表
        top_k: int = 20,  #  回前k个结果
    ) -> List[Dict]:  #  字典列表，每个字典包含id, doc_id, text, score, domain

        if doc_ids == []: # 检查 doc_ids 是否传入了一个空列表 []，不能是None，因为None是用户没有给定文档限制，不想过滤文档。【】 是空的没有文档
            return [] # 检索命中范围为空，直接返回空结果，避免无效计算。

        if self._use_memory: #  检查实例属性 _use_memory 是否为真。若为真，表明当前系统配置为使用内存存储（如 Python 列表）而非外部向量数据库。
            candidates = []  # 当系统配置为使用内存存储时，创建一个空列表
            for item in self._memory_store:  # 遍历内存中每一个文档块
                if domains and item.get("knowledge_domain") not in domains:
                    continue  # 判断用户传入 domains 且当前文档块的 knowledge_domain 字段值不在该列表中，则跳过该文档块
                if doc_ids and item.get("doc_id") not in doc_ids:  # 同上
                    continue  # 判断用户传入了 doc_ids，且当前文档块的 doc_id 不在其中，则跳过。
                dense_score = _cosine_similarity(query_dense, item.get("dense_vector", []))  # 稠密得分，计算查询稠密向量与文档块稠密向量之间的余弦相似度。若文档块无稠密向量，使用空列表作为默认值
                sparse_score = _sparse_score(query_sparse, item.get("sparse_vector", {}))  # 稀疏得分，计算查询稀疏向量与文档块稀疏向量的得分。若文档块无稀疏向量，默认为空字典。
                score = (dense_score * 0.6) + (sparse_score * 0.4)  # 混合检索的权重稠密权重0.6，稀疏权重0.4
                candidates.append(
                    {
                        "id": item["id"],           # 设置主键 id 对应的值
                        "doc_id": item["doc_id"],   # 设置文档 doc_id 对应的值
                        "text": item["chunk_text"], # 设置文本 text 对应的值
                        "score": score,  # 设置综合得分 score 对应的值
                        "domain": item.get("knowledge_domain"),  # 设置领域 domain 对应的值
                   }
                )
            candidates.sort(key=lambda value: value["score"], reverse=True)  # 按得分降序排序
            return candidates[:top_k]  # 取前 top_k 个返回。

        collection = Collection(self.collection_name)  # 通过 self.collection_name 指定的名称，创建/获取一个向量数据库（如 Milvus）的集合对象 collection，用于后续检索
        expr_parts = []  # 初始化过滤表达式列表
        if domains:  # 如果用户传入了 domains 参数（且非空），则构建对应的过滤片段。
            domain_values = '", "'.join(domains)  # 将 domains 列表中的字符串用 ", " 连接，生成指定格式的字符串
            expr_parts.append(f'knowledge_domain in ["{domain_values}"]')  # 生成一个表达式字符串，添加到expr_parts
            # 表达式字符串本身的意思是：以字符串形式存在的表达式，即不是代码中直接执行的 Python 条件语句，而是一段描述条件的文本。
            # 表达式字符串：指的是 Milvus 向量数据库里用来过滤标量字段的一种文本条件语句
            # 在你这段代码里，它的作用是在做向量相似度检索时，先筛掉不符合条件的文档块，然后再在剩下的数据里计算向量距离。这样可以
            # 精确限定检索范围
            # 提高检索速度（数据库只扫描命中的那部分数据，避免无效向量计算）。
        if doc_ids: # 判断是否需要文档 ID 过滤，有值过滤
            doc_id_values = ", ".join(str(doc_id) for doc_id in doc_ids) # 拼接文档 ID 值：将 doc_ids 中的整型转换为字符串，并用逗号空格连接，形成类似 "1, 2, 3" 的字符串。
            expr_parts.append(f"doc_id in [{doc_id_values}]")  # 生成文档 ID 过滤表达式：形如 doc_id in [1, 2, 3]，追加到 expr_parts
        expr = " and ".join(expr_parts) if expr_parts else None  # 多个条件用 and 连接；如果没有条件则为 None
        # and 连接后的样子就是一个完整、合法的 Milvus 过滤表达式字符串，由若干条件通过 and 逻辑组合而成。
        # 这个字符串最终会传递给 Milvus 的 expr 参数，用来在检索时预先过滤数据。
        # 双路，一路是dense_vec
        dense_req = AnnSearchRequest(  # 创建稠密向量搜索请求对象，用于定义稠密向量侧的近似最近邻搜索参数。
            data=[query_dense],  # 传入稠密查询向量
            anns_field="dense_vector",  # 指定存储稠密向量的字段
            param={"metric_type": "COSINE", "params": {"nprobe": 10}},  # metric_type：余弦距离，nprobe：搜索时的簇数（影响精度/性能）
            limit=top_k,  # 每个单路检索返回的记录数
            expr=expr,  # 绑定过滤表达式：将之前构造的过滤表达式传入请求，用于在检索时提前过滤。
        )  # dense_req 的初始化
        if not query_sparse: # 检测稀疏查询向量是否存在，若没有则只进行相似度检索
            results = collection.search(  # 调用纯稠密检索
                data=[query_dense], # 传入稠密向量，单查询稠密向量
                anns_field="dense_vector", # 指定稠密向量字段。
                param={"metric_type": "COSINE", "params": {"nprobe": 10}}, # metric_type：余弦距离，nprobe：搜索时的簇数（影响精度/性能）
                limit=top_k, # 返回结果数量
                expr=expr, # 绑定过滤表达式：将之前构造的过滤表达式传入请求，用于在检索时提前过滤。
                output_fields=["doc_id", "chunk_text", "knowledge_domain"],  # 指定输出字段：指定返回哪些标量字段，用于构建最终结果
            )  # 纯稠密向量检索
        else:
            # 双路二路是sparse_vec
            sparse_req = AnnSearchRequest(  # 创建稀疏搜索请求
                data=[query_sparse], # 传入稀疏查询向量
                anns_field="sparse_vector", # 指定稀疏向量字段。
                param={"metric_type": "IP"}, # 指定度量方式为 IP（内积），稀疏向量通常使用内积（Inner Product）衡量相似度
                limit=top_k,  # 稀疏侧返回数量
                expr=expr, # 过滤表达式
            )  #完成稀疏请求创建。
            # 召回，同时传入下面
            results = collection.hybrid_search(  #  调用混合检索
                reqs=[dense_req, sparse_req],  # 传入两路请求列表：包含稠密请求和稀疏请求。
                rerank=RRFRanker(k=config.HYBRID_RRF_K), # 重排序策略
                limit=top_k, # 最终返回的结果数
                output_fields=["doc_id", "chunk_text", "knowledge_domain"], # 输出字段
            ) #  同时有稠密和稀疏查询时，使用 hybrid_search
        if not results or not results[0]: # 检查结果有效性
            return []  # results[0] 是 Milvus 返回的 SearchResult 列表（第一个查询的结果集）。如果为空则返回空列表
        return [ # 开始返回结果：通过列表推导式构建与内存模式结构一致的字典列表。
            { # 构建单个结果字典
                "id": hit.id,  # Milvus 中实体的主键 ID
                "doc_id": hit.entity.get("doc_id"), # 标量字段 doc_id
                "text": hit.entity.get("chunk_text"), #  获取文本
                "score": hit.score, #  命中结果的相似度分值
                "domain": hit.entity.get("knowledge_domain"), #读取 knowledge_domain 字段
            }
            for hit in results[0]
        ]  # 列表推导式：将每个 hit 转换为统一的字典格式，与内存模式返回的结构一致。

    def upsert(self, data: List[Dict]) -> List[int]:  # 定义函数 upsert，用于封装可复用的逻辑。
        """处理upsert相关逻辑。

        参数：
            data: 当前函数使用的输入参数。
        """
        if self._use_memory:  # 根据条件决定是否执行下面的代码块。
            inserted_ids = []  # 设置 inserted_ids 的值，供后续逻辑使用。
            with self._lock:  # 通过上下文管理器安全地使用资源。
                for item in data:  # 遍历目标数据中的每一项。
                    item_id = self._id_counter  # 设置 item_id 的值，供后续逻辑使用。
                    self.__class__._id_counter += 1  # 执行这一行代码，完成当前逻辑。
                    self._memory_store.append({"id": item_id, **item})  # 调用 self._memory_store.append 处理当前这一步逻辑。
                    inserted_ids.append(item_id)  # 调用 inserted_ids.append 处理当前这一步逻辑。
            return inserted_ids  # 返回当前函数计算出的结果。

        if not data:  # 根据条件决定是否执行下面的代码块。
            return []  # 返回当前函数计算出的结果。

        collection = Collection(self.collection_name)  # 调用 Collection 并把结果保存到 collection 中。
        has_primary_key = any("id" in item and item.get("id") is not None for item in data)  # 调用 any 并把结果保存到 has_primary_key 中。
        if has_primary_key:  # 根据条件决定是否执行下面的代码块。
            result = collection.upsert(data)  # 调用 collection.upsert 并把结果保存到 result 中。
        else:  # 当前面的条件都不满足时，执行这里的代码块。
            result = collection.insert(data)  # 调用 collection.insert 并把结果保存到 result 中。
        collection.flush()  # 调用 collection.flush 处理当前这一步逻辑。
        primary_keys = getattr(result, "primary_keys", None)  # 调用 getattr 并把结果保存到 primary_keys 中。
        return list(primary_keys or [])  # 返回当前函数计算出的结果。

    def delete_by_doc_id(self, doc_id: int):  # 定义函数 delete_by_doc_id，用于封装可复用的逻辑。
        """删除bydocid相关逻辑。

        参数：
            doc_id: 当前函数使用的文档 ID。
        """
        if self._use_memory:  # 根据条件决定是否执行下面的代码块。
            self.__class__._memory_store = [  # 设置 self.__class__._memory_store 的值，供后续逻辑使用。
                item for item in self._memory_store if item.get("doc_id") != doc_id  # 执行这一行代码，完成当前逻辑。
            ]  # 结束当前列表、字典、元组、调用或代码块。
            return  # 结束当前函数并返回空结果。

        collection = Collection(self.collection_name)  # 调用 Collection 并把结果保存到 collection 中。
        collection.delete(f"doc_id == {doc_id}")  # 调用 collection.delete 处理当前这一步逻辑。






