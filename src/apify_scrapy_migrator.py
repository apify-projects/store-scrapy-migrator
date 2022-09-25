import os
import shutil
import sys
import argparse

from create_files import create_dockerfile, create_main_py, create_apify_json, create_input_schema, create_readme, \
    update_reqs


def parse_input():
    """
    Parses input from the CLI
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--migrate", help="Wraps scrapy project with files to be pushed to Apify platform",
                        type=str, dest='migrate_folder')
    parser.add_argument("-i", "--update-input", help="Creates or updates 'INPUT_SCHEMA.json'. Default value is '.'",
                        type=str, dest='input_folder', const='.', nargs='?')
    parser.add_argument("-r", "--update-reqs", help="Creates or updates 'requirements.txt'. Default value is '.'",
                        type=str, dest='reqs_folder', const='.', nargs='?')
    args = parser.parse_args()

    if args.migrate_folder:
        # whole wrap
        wrap_scrapy(args.migrate_folder)
    else:
        # updates
        if args.input_folder:
            create_or_update_input(args.input_folder)
        if args.reqs_folder:
            update_reqs(args.reqs_folder)


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
            answer = sys.stdin.readline().strip()[0]
            if not (answer == 'y' or answer == 'Y'):
                return False
            else:
                break

    spider_dir = get_spiders_folder(dst)

    # could not find spider class
    if not spider_dir:
        return False

    spiders = get_spider_classes(spider_dir)

    # found one spider class
    if len(spiders) == 1:
        return create_or_update_input(dst, spiders[0]) and create_dockerfile(dst) \
            and create_apify_json(dst) and create_main_py(dst, spiders[0][0], spiders[0][1]) \
            and update_reqs(dst) and create_readme(dst, spiders[0][0])

    # found multiple spider classes
    spider_names = [spider[0] for spider in spiders]
    copy_files(dst, spiders)

    for spider in spiders:
        dst_of_spider = os.path.join(dst, spider[0])
        create_or_update_input(dst_of_spider, spider) and create_dockerfile(dst_of_spider) \
        and create_apify_json(dst_of_spider) and create_main_py(dst_of_spider, spider[0], spider[1]) \
        and update_reqs(dst_of_spider) and create_readme(dst_of_spider, spider[0])


def copy_files(dst, spiders):
    """
    Copy scrapy project. git files are ignored
    :param dst: destination of scrapy project
    :param spiders: tuple of names of (spider_name, spider_file)
    """

    # folder_names
    script_files = [os.path.split(arr[1])[1] for arr in spiders]
    spider_names = [arr[0] for arr in spiders]

    # copy files inside the project without script files
    first_copy_name = os.path.join(dst, spiders[0][0])
    shutil.copytree(dst, first_copy_name,
                    ignore=shutil.ignore_patterns('.git*', '.scrapy', *script_files, spider_names[0]))

    # create copies of the first copy and add script file
    # for name in spider_names[1:]:
    #    shutil.copytree(first_copy_name, os.path.join(dst, name), ignore=shutil.ignore_patterns('.git*'))
    #    shutil.copy(spiders[0][1], os.path.join(dst, name))

    for i in range(1, len(spider_names)):
        shutil.copytree(first_copy_name, os.path.join(dst, spider_names[i]), ignore=shutil.ignore_patterns('.git*'))
        shutil.copy(spiders[i][1], get_spiders_folder(os.path.join(dst, spider_names[i])))

    # add script file to the first copy
    shutil.copy(spiders[0][1], get_spiders_folder(first_copy_name))


def get_scrapy_list(dst):
    """
    Runs a "scrapy list" command in directory and extracting spider names to list
    :param dst: destination of directory
    :returns: list of spider names in str
    """
    # run "scrapy list" in scrapy directory and save stdout to variable
    stdout = str(subprocess.run(["scrapy", "list"], cwd=f'{os.path.abspath(dst)}', stdout=subprocess.PIPE).stdout)

    # remove first two chars "'b" and last char "'" created by converting bytecode to string
    stdout_stripped = stdout[2:-1]

    # remove carriage return to make next lines work both on Windows and Linux
    stdout_remove_cr = stdout_stripped.replace('\\r', '\\n')

    # split result by newline and remove last empty element
    stdout_split = stdout_remove_cr.split('\\n')[:-1]

    return stdout_split


def is_name_unique(client, name):
    """
    Check if migrated project name is unique, otherwise `apify push` is going to overwrite existing project
    :param client: client class of ApifyClient
    :param name: name of the migrated project name
    """

    # check name from list of all client actors
    names = [actor['name'] for actor in client.actors().list().items]
    return not (name in names)


def create_or_update_input(dst, spider_tuple=None):
    """
    Creates or updates INPUT_SCHEMA.json of a project. Tries to find a spider class if spider_tuple is not provided
    :param dst: destination of scrapy project
    :param spider_tuple: tuple of (spider_name, spider_destination)
    :return: boolean of successfulness
    """

    if spider_tuple is None:
        spider_tuple = get_spider_classes(spiders_dir)

        if len(spiders) == 0:
            print('No spiders found in "spiders" subdirectory.')
            return None

        if len(spiders) > 1:
            print('Multiple spiders in one directory found. This method requires only one.')
            return None

    inputs = get_inputs(spider_tuple[1])

    return create_input_schema(os.path.join(dst), spider_tuple[0], inputs)


def update_input(dst, spider):
    inputs = get_inputs(spider)
    create_input_schema(dst, spider, inputs)


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

    if spiders_dir is None:
        print('Could not find any spider folder in', dst)

    return spiders_dir


def get_spider_classes(spiders_dir):
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


def get_inputs(filename):
    """
    Finds input in a file
    :param filename: filename
    :return: array of tuple (name, default_value) of inputs
    """
    file = open(filename, 'r')
    lines = file.readlines()
    getattr_self = 'getattr(self'
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
        if getattr_self in lines[index]:
            value = get_input(lines[index])
            if value:
                inputs.append(value)
        index += 1

    return inputs


# possibly obsolete
def check_inputs(inputs):
    if len(inputs) == 0:
        return inputs

    print('Inputs found:')

    for i in range(1, len(inputs)):
        print(str(inputs[i][0]), end=' ')
        if inputs[i][1]:
            print('with default value: ' + str(inputs[i][1]))
        else:
            print('without default value')

    print('Do you want to edit inputs? [Y/N]')
    answer = sys.stdin.readline().strip()
    if not (answer == 'n' or answer == 'N'):
        return inputs


def get_input(line):
    """
    Tries to retrieve name and the default value from the getattr() call
    :param line: line with getattr() method call
    :return: tuple of name,default value. None if value could not retrieve
    """
    getattr_self = 'getattr(self'
    try:
        index = line.index(getattr_self) + len(getattr_self)
    except ValueError:
        # getattr() was not found
        return None

    # find second argument of getattr
    while index < len(line) and line[index] != ',':
        index += 1

    # could not find recognizable
    if index >= len(line):
        return None

    name, index = get_attr_name(line, index + 1)

    if index is None:
        return None

    default_value = get_default_value(line, index)

    return name, default_value


def get_attr_name(line, index):
    """
    Gets attribute name from line until comma. Name can be variable name or string
    :param line: string of a text
    :param index: index of a first letter of a text
    :return: tuple of name and index of the fist non-name letter. I name/index is None, then could not find name
    """
    if index >= len(line):
        return None, None

    # skip white spaces
    while index < len(line) and line[index].isspace():
        index += 1

    if index == len(line):
        return None, None

    # get name
    name = ''
    first_quotes = -1
    quotes = ''

    # read until find quotes
    while index < len(line) and line[index] != '\'' and line[index] != '"' and line[index] != ',':
        name += line[index]
        index += 1

    if index == len(line) or line[index] == ',':
        # couldn't find quotes
        return None, None
    elif line[index] == '\'':
        quotes = '\''
        first_quotes = index
    elif line[index] == '"':
        quotes = '"'
        first_quotes = index

    # find second quotes
    index += 1
    while index < len(line) and line[index] != quotes:
        index += 1

    name = line[first_quotes + 1:index].strip()
    index += 1

    return name, index


def get_default_value(line, index):
    """
    Get default value from the getattr function
    :param line: string of a text
    :param index: index of a first letter of a text
    :return: default value of None if default value cannot be located or recognized
    """
    if index >= len(line):
        return None

    # try to find string or int
    while index < len(line) and \
            not (line[index] == '\'' or line[index] == '"' or line[index] == '-' or line[index].isdigit()):
        index += 1

    # check if quotes were found
    quotes = None
    if index >= len(line):
        return None
    elif line[index] == '\'':
        quotes = '\''
    elif line[index] == '"':
        quotes = '"'

    # call respective method based on type
    if quotes is not None:
        return get_default_string_value(line, index, quotes)
    elif line[index] == '-' or line[index].isdigit():
        return get_default_number_value(line, index)

    return None


def get_default_string_value(line, index, quotes):
    """
    Find default string value of an attribute
    :param line: line with default string value
    :param index: current index on the line
    :param quotes: type of quotes
    """
    index += 1
    first_char = index

    # read until second quote
    while index < len(line) and line[index] != quotes:
        index += 1

    if index >= len(line):
        return None

    return line[first_char: index]


def get_default_number_value(line, index):
    """
    Find default number value of an attribute
    :param line: line with default string value
    :param index: current index on the line
    """
    negative = False

    if line[index] == '-':
        negative = True
        index += 1
    first_digit_index = index

    # read until index is on a digit
    while index < len(line) and line[index].isdigit():
        index += 1

    if index >= len(line):
        return None

    # decimal numbers not supported, convert to string
    if line[index] == '.':
        index += 1
        # read decimal points
        while index < len(line) and line[index].isdigit():
            index += 1
        if index >= len(line):
            return None
        if negative:
            first_digit_index -= 1

        return line[first_digit_index:index]

    num = int(line[first_digit_index:index])
    if negative:
        num *= -1
    return num


if __name__ == '__main__':  # for debug purposes
    wrap_scrapy(r"C:\Users\Hoang\Desktop\bc\scrapy-project")
