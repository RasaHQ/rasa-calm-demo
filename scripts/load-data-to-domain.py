from datasets import load_dataset
import logging
import yaml
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sentence_to_snake_case(sentence):
    # Remove punctuation and split the sentence into words
    words = sentence.split()
    words = [word.strip('.,?!()[]{}""\'') for word in words]
    
    # Join the words with underscores and convert to lowercase
    snake_case = '_'.join(words).lower()
    
    return snake_case[:50]

def load_dataset_to_domain(dataset_name):
    dataset = load_dataset(dataset_name)['train']
    logger.info(f"✅ Dataset")

    responses = {}
    for qna in tqdm(dataset):
        question = qna['question']
        answer = qna['answers']['text'][0]

        # Create a unique ID for the response
        response_id = f'utter_{sentence_to_snake_case(question)}'

        # Add the response to the responses dictionary
        if response_id not in responses:
            responses[response_id] = []
        
        responses[response_id].append({
            'text': answer.replace('\n', ' '),
        })

    faq_yaml = {'version': '3.1', 'responses': responses}

    # save file
    with open('domain/squad.yml', 'w') as f:
        yaml.dump(faq_yaml, f, indent=4)

if __name__ == "__main__":
    load_dataset_to_domain("rajpurkar/squad")
    logger.info(f"✅ Done")

    