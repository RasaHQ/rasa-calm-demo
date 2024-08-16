from datasets import load_dataset
from langchain.schema import Document
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores.qdrant import Qdrant
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def excel_to_documents(excel_path):
    df = pd.read_excel(excel_path)
    documents = []
    for _, row in df.iterrows():
        documents.append(Document(
            page_content=row['question'],
            metadata={
                'type': 'faq',
                'answer': row['answer'],
                'id': row['id'],
                'title': row['title'],
            }))
    return documents

def load_dataset_to_qdrant(excel_file_path):
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={"device": 'cpu'},
        encode_kwargs={'normalize_embeddings': True},
    )
    logger.info(f"✅ Embeddings")

    docs = excel_to_documents(excel_file_path)
    return Qdrant.from_documents(
        docs,
        embeddings,
        host="localhost",
        prefer_grpc=True, 
        collection_name="squad",
    )

if __name__ == "__main__":
    qdrant = load_dataset_to_qdrant("path_to_excel_file.xlsx")
    logger.info(f"✅ Qdrant")
    result = qdrant.similarity_search_with_score("Who built Notre Dame?")
    logger.info(f"Qdrant search result:")
    logger.info(result)