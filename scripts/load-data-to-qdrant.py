from datasets import load_dataset
from langchain.schema import Document
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores.qdrant import Qdrant
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def dataset_to_documents(dataset):
    documents = []
    for i in range(len(dataset)):
        documents.append(Document(
            page_content=dataset[i]['question'], 
            metadata={
                'type': 'faq',
                'answer': dataset[i]['answers']['text'][0],
                'id': dataset[i]['id'],
                'title': dataset[i]['title'],
            }))
    return documents

def load_dataset_to_qdrant(dataset_name):
    squad = load_dataset(dataset_name)
    logger.info(f"✅ Dataset")

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={"device": 'cpu'},
        encode_kwargs={'normalize_embeddings': True},
    )
    logger.info(f"✅ Embeddings")

    docs = dataset_to_documents(squad['train'])
    return Qdrant.from_documents(
        docs,
        embeddings,
        host="localhost",
        prefer_grpc=True, 
        collection_name="squad",
    )

if __name__ == "__main__":
    qdrant = load_dataset_to_qdrant("rajpurkar/squad")
    logger.info(f"✅ Qdrant")
    result = qdrant.similarity_search_with_score("Who built Notre Dame?")
    logger.info(f"Qdrant search result:")
    logger.info(result)