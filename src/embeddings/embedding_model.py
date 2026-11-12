
from sentence_transformers import SentenceTransformer


class EmbeddingModel:

    def __init__(
        self,
        model_name="BAAI/bge-small-zh-v1.5",
        device="cpu"
    ):
        self.model = SentenceTransformer(
            model_name,
            device=device
        )

    def embed_documents(self, texts):
        return self.model.encode(
            texts,
            normalize_embeddings=True
        )

    def embed_query(self, query):
        return self.model.encode(
            query,
            normalize_embeddings=True
        )
