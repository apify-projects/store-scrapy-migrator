import os
import sys
import argparse
import subprocess

from .create_files import create_dockerfile, create_main_py, create_apify_json, create_input_schema


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
        wrap_scrapy(args.migrate_folder)
    else:
        if args.input_folder:
            _get_and_update_spiders_and_input(args.input_folder)
        if args.reqs_folder:
            update_reqs(args.reqs_folder)


def update_reqs(dst):
    """
    Creates or updates requirements.txt of a project. Runs pipreqs. If requirements exists, appends with pipreqs result
    :param dst: destination of scrapy project
    :return: boolean of successfulness
    """

    # check correct dst
    if not os.path.exists(os.path.join(dst, 'scrapy.cfg')):
        print('Select root directory with "scrapy.cfg" file.')
        return False

    import pipreqs
    reqs_file = os.path.join(dst, 'requirements.txt')

    # check if requirements.txt exists
    if not os.path.exists(os.path.join(dst, 'requirements.txt')):
        subprocess.run(["pipreqs", dst], stderr=subprocess.DEVNULL)
        with open(reqs_file, 'r') as reqs:
            unsafe_split_lines = [x.split('==') for x in reqs.read().splitlines(keepends=False)]
            lines = remove_invalid_reqs(unsafe_split_lines)
        with open(reqs_file, 'w') as reqs:
            reqs.writelines([x[0] + '==' + x[1] + '\n' for x in lines])
        print('Created requirements.txt')
        return True

    # create tmp file to save user requirements and call pipreqs
    reqs_tmp = os.path.join(dst, '.tmp_reqs.tmp_apify')

    if os.path.exists(reqs_tmp):
        # if tmp file exists, removes it. It should be created only in runs before and shouldn't be user's file.
        os.remove(reqs_tmp)

    os.rename(reqs_file, reqs_tmp)
    subprocess.run(["pipreqs", dst], stderr=subprocess.DEVNULL)

    # check for duplicates
    with open(reqs_file, 'r') as reqs:
        reqs_lines = reqs.read().splitlines(keepends=False)
    with open(reqs_tmp, 'r') as tmp:
        tmp_lines = tmp.read().splitlines(keepends=False)

    complete_reqs = concat_dedup_reqs(reqs_lines, tmp_lines)

    with open(reqs_file, 'w') as reqs:
        for req in complete_reqs:
            reqs.write(req + '\n')

    os.remove(reqs_tmp)
    print('Created requirements.txt')
    return True


def concat_dedup_reqs(reqs_lines, tmp_lines):
    """
    Check lines of requirements and concatenates them and removes duplicates
    :param reqs_lines array of lines of the first requirements file
    :param tmp_lines array of lines of the second requirements file
    """
    # split module name and version number
    reqs_arr = [line.split('==') for line in reqs_lines]
    unsafe_tmp_arr = [line.split('==') for line in tmp_lines]

    # removes modules with non-numeric version
    # bug of pipreqs which adds 'apify_scrapy_executor.egg==info' to requirements
    tmp_arr = remove_invalid_reqs(unsafe_tmp_arr)

    res = []
    status = ('', -1)

    for req in reqs_arr:
        # skips modules with non-numeric version
        if not is_valid_version(req[1]):
            continue

        for i in range(len(tmp_arr)):
            if req[0] in tmp_arr[i]:
                # duplicate name found
                status = ('duplicate', i)
                if req[1] == tmp_arr[i][1]:
                    # same version
                    res.append(req[0] + '==' + req[1])
                else:
                    # choose higher version
                    res.append(req[0] + '==' + get_higher_version(req[1], tmp_arr[i][1]))
                break
            else:
                # not duplicate
                res.append(req[0] + '==' + req[1])

        if status[0] == 'duplicate':
            # remove duplicate from tmp
            tmp_arr.remove(tmp_arr[status[1]])
            status = ('', -1)

    # append reqs left in tmp
    for req_left in tmp_arr:
        res.append(req_left[0] + '==' + req_left[1])

    return res


def remove_invalid_reqs(req_lines):
    """
    Removes modules with non-numeric version. Bug of pipreqs which adds 'apify_scrapy_executor.egg==info'
    :param req_lines lines from requirements file
    :returns array of safe lines
    """
    safe_lines = []
    for req in req_lines:
        if is_valid_version(req[1]):
            safe_lines.append(req)
    return safe_lines


def is_valid_version(v):
    """
    Check if all values of version number separated by '.' is a numeric value
    :returns boolean
    """
    return not (False in [x.isnumeric() for x in v.split('.')])


def get_higher_version(v1, v2):
    """
    Compares two versions and returns the higher one
    :param v1 first version
    :param v2 second version
    :returns str of one of the versions
    """
    v1_split = v1.split('.')
    v2_split = v2.split('.')
    for i in range(len(v1_split)):
        if int(v1_split[i]) > int(v2_split[i]):
            return v1
        elif int(v1_split[i]) < int(v2_split[i]):
            return v2

    # if equal then returns first one
    return v1


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
            else:
                break

    spiders, inputs = _get_and_update_spiders_and_input(dst)

    return create_dockerfile(dst) and create_apify_json(dst) and create_main_py(dst, spiders[0][0], spiders[0][1]) \
        and update_reqs(dst)


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
    while index < len(line) and not (
            line[index] == '\'' or line[index] == '"' or line[index] == '-' or line[index].isdigit()):
        index += 1

    quotes = None
    if index >= len(line):
        return None
    elif line[index] == '\'':
        quotes = '\''
    elif line[index] == '"':
        quotes = '"'

    if quotes is not None:
        index += 1
        first_quotes = index
        while index < len(line) and line[index] != quotes:
            index += 1
        if index >= len(line):
            return None
        return line[first_quotes: index]
    elif line[index] == '-' or line[index].isdigit():
        negative = False
        if line[index] == '-':
            negative = True
            index += 1
        first_digit = index
        while index < len(line) and line[index].isdigit():
            index += 1

        if index >= len(line):
            return None
        elif line[index] == '.':
            # decimal numbers not supported, convert to string
            index += 1
            while index < len(line) and line[index].isdigit():
                index += 1
            if index >= len(line):
                return None
            if negative:
                first_digit -= 1
            return line[first_digit:index]

        num = int(line[first_digit:index])
        if negative:
            num *= -1
        return num


if __name__ == '__main__': # for debug purposes
    parse_input()
