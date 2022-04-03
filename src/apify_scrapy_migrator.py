import os
import sys

from create_files import create_dockerfile, create_main_py, create_apify_json, create_input_schema


def migrate():
    """
    Prepares scrapy project for migration to Apify platform. Call only from cmd. Requires a directory name argument
    """
    if len(sys.argv) < 2:
        print('Missing directory name argument')
        sys.exit(2)

    dir_with_scrapy = sys.argv[1]

    if not os.path.isdir(dir_with_scrapy):
        print('Argument is not a directory')
        sys.exit(2)

    if not wrap_scrapy(sys.argv[1]):
        sys.exit(1)

    print('Migration successful')


def update_input():
    """
    Creates or updates INPUT_SCHEMA.json of a project. Call only from cmd. Requires a directory name argument
    """
    if len(sys.argv) < 2:
        print('Missing directory name argument')
        sys.exit(2)

    if _get_and_update_spiders_and_input(sys.argv[1]) is None:
        sys.exit(1)

    print('Input updated successfully')


def _get_and_update_spiders_and_input(dst):
    """
    Creates or updates INPUT_SCHEMA.json of a project
    :param dst: destination of scrapy project
    :return: tuple of (name, path) of spider and tuple of (name, default_value) of inputs
    """
    # TODO: Should I expect other spiders dir location?
    spiders_dir = get_spiders_folder(dst)

    if not spiders_dir:
        print("Cannot find subdirectory 'spiders'.")
        return None

    # TODO: What to do if multiple spiders? Maybe create multiple directory with as individual actors
    spiders = get_spiders(spiders_dir)

    if len(spiders) == 0:
        print('No spiders found in "spiders" subdirectory.')
        return None

    inputs = get_inputs(spiders[0][1])
    create_input_schema(dst, spiders[0][0], inputs)

    return spiders, inputs


def wrap_scrapy(dst: str):
    """
    Wrap scrapy project with files to be executable on Apify platform
    :param dst: directory which will be wrap with files
    """

    files_in_dir = os.listdir(dst)
    files = ['requirements.txt', 'main.py', 'Dockerfile', 'apify.json', 'INPUT_SCHEMA.json']

    # check if in scrapy root folder
    if 'scrapy.cfg' not in files_in_dir:
        print('Select root directory with "scrapy.cfg" file.')
        return False

    # check if files that will be created exist
    for file in files:
        if file in files_in_dir:
            print("If these files exists, they will be overwritten: 'requirements.txt', 'main.py', 'Dockerfile', "
                  "'apify.json', 'INPUT_SCHEMA.json'. Do you wish to continue? [Y/N]")
            answer = sys.stdin.read(1)[0]
            if not (answer == 'y' or answer == 'Y'):
                return False

    spiders, inputs = _get_and_update_spiders_and_input(dst)

    is_correct = True
    if spiders is not None:
        is_correct = create_input_schema(dst, spiders[0][0], inputs)

    if not is_correct:
        return False

    return create_dockerfile(dst) and create_apify_json(dst) and create_main_py(dst, spiders[0][0], spiders[0][1])


def get_spiders_folder(dst):
    """
    Finds spiders folder in scrapy root directory
    :param dst:  scrapy root directory
    :return:  returns path to spiders folder or None
    """
    spiders_dir = None
    for directory in os.listdir(dst):
        if os.path.isdir(os.path.join(dst, directory, 'spiders')):
            spiders_dir = os.path.join(dst, directory, 'spiders')
            break

    return spiders_dir


def get_spiders(spiders_dir):
    """
    Find classes with scrapy.Spider argument in spiders directory
    :param spiders_dir: spiders directory
    :return: array of tuples of (name, path) of spider classes
    """
    spiders = []

    for file in os.listdir(spiders_dir):
        if file.endswith(".py"):
            file_to_read = open(os.path.join(spiders_dir, file), 'r')
            for line in file_to_read.readlines():
                stripped = line.strip()
                if stripped.startswith('class') and stripped.endswith('(scrapy.Spider):'):
                    class_name = stripped.split(' ')[1].split('(')[0]
                    spiders.append((class_name, os.path.join(spiders_dir, file)))
                    break  # TODO: is break OK? I think its better than rewriting it with while loop

    return spiders


def print_help():
    """
    Prints help. Call only from cmd.
    """
    help_text = """Apify scrapy migrator wraps scrapy project with files so it can be migrated to Apify platform.

USAGE
    $ apify_scrapy_migrator [COMMAND] destination

COMMANDS
    migrate         Wraps scrapy project with files to be migrated to Apify platform.
    update-input    Creates or updates INPUT_SCHEMA.json of spider project.
    help            Prints this help.

"""
    print(help_text)


def get_inputs(filename):
    """
    Finds input in a file
    :param filename: filename
    :return: array of tuple (name, default_value) of inputs
    """
    file = open(filename, 'r')
    lines = file.readlines()
    GETATTR_SELF = 'getattr(self'
    index = 0

    # find class with spider
    while index < len(lines) and not lines[index].lstrip().startswith('class') and 'scrapy.Spider' not in lines[index]:
        index += 1
    if index >= len(lines):
        return []

    inputs = []

    # find getattr in the current class
    index += 1
    while index < len(lines) and not lines[index].lstrip().startswith('class'):
        if GETATTR_SELF in lines[index]:
            value = get_input(lines[index])
            if value:
                inputs.append(value)
        index += 1

    return inputs


def get_input(line):
    """
    Tries to retrieve name and the default value from the getattr() call
    :param line: line with getattr() method call
    :return: tuple of name,default value. None if value could not retrieve
    """
    GETATTR_SELF = 'getattr(self'
    try:
        index = line.index(GETATTR_SELF) + len(GETATTR_SELF)
    except ValueError:
        # getattr() was not found
        return None

    # find second argument of getattr, which is string of the attribute name
    while index < len(line) and line[index] != '"' and line[index] != "'":
        index += 1

    if index >= len(line):
        return None

    index += 1
    start_index = index
    # find second quotation marks of the attribute name
    while index < len(line) and line[index] != '"' and line[index] != "'":
        index += 1

    if index >= len(line):
        return None

    name = line[start_index:index]

    # TODO: int
    # TODO: default value for other types than str: [str]? [int]?
    index += 1
    # try to find default value
    while index < len(line) and line[index] != '"' and line[index] != "'":
        index += 1

    if index >= len(line):
        return name, None

    # default value found
    index += 1
    start_index = index
    while index < len(line) and line[index] != '"' and line[index] != "'":
        index += 1

    if index >= len(line):
        return None

    return name, line[start_index:index]


if __name__ == '__main__':
    _get_and_update_spiders_and_input(r'./../../scrapy_project/')
