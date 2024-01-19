import asyncio
from rasa_plus.cli.e2e_test import read_test_cases 
from rasa.shared.core.domain import Domain
from rasa.core.nlg.response import TemplatedNaturalLanguageGenerator
from rasa.shared.core.trackers import DialogueStateTracker

async def convert_test_case_to_conversation(domain: Domain, test_cases_path: str):
    """Converts a test case to a conversation transcript.

    Prints the conversation transcripts to the console. The transcripts are 
    in the format of "user: ... bot: ...".
    
    Args:
        domain: the domain of the assistant
        test_cases_path: the path to the test cases file

    Returns:
        None"""
    input_test_cases = read_test_cases(test_cases_path)
    generator = TemplatedNaturalLanguageGenerator(domain.responses)

    for test_case in input_test_cases:
        # replace utterance templates with actual messages in the test case
        transcript = ""
        for step in test_case.steps:
            if step.actor == "bot" and not step.text:
                tracker = DialogueStateTracker.from_events("empty", [])
                generated = await generator.generate(step.template, tracker, "shell")
                text = generated.get("text") if generated else step.template
            else:
                text = step.text

            transcript += f"{step.actor}: {text}\n"
        
        print(transcript)
        print("\n\n")


if __name__ == "__main__":
    domain = Domain.load("domain.yml")
    
    asyncio.run(convert_test_case_to_conversation(domain, "tests/e2e_test_stories.yml"))
