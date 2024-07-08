import json
import os
import yaml


def extract_unique_test_full_names(jsonl_file_path):
    unique_test_full_names = set()

    with open(jsonl_file_path, 'r', encoding='utf-8') as file:
        for line in file:
            data = json.loads(line)
            test_full_name = data.get('test_name').strip()
            if test_full_name:
                unique_test_full_names.add(test_full_name)

    print(f"{len(unique_test_full_names)} unique e2e tests found in {jsonl_file_path}.")

    return unique_test_full_names


def find_yaml_files(directory):
    yaml_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.yml') or file.endswith('.yaml'):
                yaml_files.append(os.path.join(root, file))
    return yaml_files


def copy_unmatched_test_cases(yaml_files, unique_test_full_names, destination_dir):
    for file_path in yaml_files:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = yaml.safe_load(file)
            test_cases = content.get('test_cases', [])
            new_test_cases = []

            for test_case in test_cases:
                test_case_name = test_case['test_case']
                if test_case_name not in unique_test_full_names:
                    new_test_cases.append(test_case)
                else:
                    print(f"Test case '{test_case_name}' was present in train data set.")

            if new_test_cases:
                destination_file_path = os.path.join(destination_dir,
                                                     os.path.basename(file_path))
                new_content = {'test_cases': new_test_cases}
                with open(destination_file_path, 'w', encoding='utf-8') as out_file:
                    yaml.dump(new_content, out_file)


def main():
    jsonl_file_path = '3_train_test_split/by_test_name/train.jsonl'
    yaml_directory = '../e2e_tests/'
    destination_directory = '.'

    os.makedirs(destination_directory, exist_ok=True)

    unique_test_full_names = extract_unique_test_full_names(jsonl_file_path)
    yaml_files = find_yaml_files(yaml_directory)

    copy_unmatched_test_cases(yaml_files, unique_test_full_names, destination_directory)

    print("Process completed. Unmatched test cases have been copied.")


if __name__ == "__main__":
    main()