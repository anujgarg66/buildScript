from threading import Thread
from subprocess import Popen, PIPE, STDOUT
import json
import os
import zipfile
import argparse
import queue
import glob
from distutils.dir_util import copy_tree
import shutil


def write_files(args):
    """
    Writes the environment/manifest/package files.
    :param args: Command line args
    """
    # Path defination for all the files

    if os.path.sep == "/":
        build_path = 'modules/build'
        ui_env_path = 'modules/aic-ui'
        bg_env_path = 'modules/aic-bg/config'
        manifest_path = 'modules/extension'
        settings_path = 'modules/aic-ui-utils/aic_settings'
    else:
        build_path = 'modules\\build'
        ui_env_path = 'modules\\aic-ui'
        bg_env_path = 'modules\\aic-bg\\config'
        manifest_path = 'modules\\extension'
        settings_path = 'modules\\aic-ui-utils\\aic_settings'

    # File Names with their path
    templates_file = os.path.join(build_path, 'templates.json')
    ui_env_file = os.path.join(ui_env_path, '.env')
    bg_env_file = os.path.join(bg_env_path, 'dev.env.json') if args.dev else os.path.join(
        bg_env_path, 'prod.env.json')
    manifest_file = os.path.join(manifest_path, 'manifest.json')
    settings_env_file = os.path.join(settings_path, '.env')

    if args.version:
        version_number = args.version.strip()
    else:
        with open('VERSION', "r") as version:
            version_number = version.read().strip()

    # template file read and storing in variable
    with open(templates_file, "r") as templates:
        template_data = json.load(templates)

    # Coditions checking
    if args.genesys.strip() not in template_data['genesys'] or args.okta.strip() not in template_data['okta'] or args.extension.strip() not in template_data['extension']['settings']:
        print(' [e] Invalid Arguments Provided to Build')
        exit(1)

    # UI object for env file is being created
    final_ui_object = template_data['uiDefault']
    final_ui_object['REACT_APP_DEBUGING'] = args.dev
    final_ui_object['REACT_APP_VERSION'] = version_number
    final_ui_object['GENERATE_SOURCEMAP'] = args.dev
    print(' [i] Template Data wrote into UI object')

    # Writing the UI env object in file
    ui_env_data = ''
    for key, value in final_ui_object.items():
        object_data = json.dumps(value) if isinstance(
            value, bool) else str(value)
        ui_env_data = ui_env_data + str(key) + '=' + object_data + '\n'

    with open(ui_env_file, "w") as ui_file:
        ui_file.write(ui_env_data)
    print(' [i] UI env file written successfully')

    # BG object for env file is being created
    bg_env_data = {}
    bg_env_data.update(template_data['backgroundDefault'])
    bg_env_data.update(template_data['genesys'][args.genesys.strip()])
    bg_env_data.update(template_data['okta'][args.okta.strip()])
    if args.dev:
        bg_env_data.update(template_data['backgroundDev'])
    if args.chrome_store:
        bg_env_data.update(template_data['buildTypes']['chrome-store'])
    else:
        bg_env_data.update(template_data['buildTypes']['default'])

    bg_env_data.update({'VERSION': version_number})

    # Writing the BG env object in file

    with open(bg_env_file, "w", encoding="utf-8") as bg_file:
        json.dump(bg_env_data, bg_file, indent=4, ensure_ascii=False)

    print(" [i] Background Data wrote Successfully")

    # Manifest Object is created
    build_name = template_data['extension']['settings'][args.extension.strip(
    )]['name']
    final_extension_manifest = template_data['extension']['default']
    if args.support:
        final_extension_manifest['options_page'] = 'settings.html'
    final_extension_manifest['name'] = build_name
    final_extension_manifest['version'] = version_number

    # Writing the manifest json object to file

    with open(manifest_file, "w", encoding="utf-8") as manifest:
        json.dump(final_extension_manifest, manifest,
                  indent=4, ensure_ascii=False)

    print(" [i] Manifest JSON file wrote Successfully")

    if args.support:
        settings_env_data = ''
        setting_dev_default = template_data['settingsDevDefault']
        for key in setting_dev_default:
            object_data = json.dumps(setting_dev_default[key]) if isinstance(
                setting_dev_default[key], bool) else str(setting_dev_default[key])
            settings_env_data = settings_env_data + \
                str(key) + '=' + object_data + '\n'

        with open(settings_env_file, "w") as settings_file:
            settings_file.write(settings_env_data)
        print(' [i] Settings env file wrote successfully')

    if args.release:
        # Reading and Writing Package.json file
        with open('package.json', "r") as package_json:
            package_data = json.load(package_json)

        package_data['version'] = version_number

        with open('package.json', "w", encoding="utf-8") as build_package:
            json.dump(package_data, build_package, indent=4)
        print(" [i] Package JSON file wrote Successfully")

        # Reading and writing lerna.json file
        with open('lerna.json', "r") as lerna_json:
            lerna_data = json.load(lerna_json)

        lerna_data['version'] = version_number

        with open('lerna.json', "w", encoding="utf-8") as build_lerna:
            json.dump(lerna_data, build_lerna, indent=4)
        print(" [i] Lerna JSON file wrote Successfully")

    return 0


def get_all_file_paths(directory):
    """
    Get the List of All files and directories needs to be zipped
    :param args: direcotry to be zipped
    """
    file_paths = []

    for root, _, files in os.walk(directory):
        for filename in files:
            filepath = os.path.join(root, filename)
            file_paths.append(filepath)

    return file_paths


def zip():
    """
    Zip the Entire extension directory
    """
    directory = 'modules\\extension' if os.path.sep == "\\" else 'modules/extension'
    manifest_file = os.path.join(directory, 'manifest.json')
    release_path = 'releases'

    # calling function to get all file paths in the directory
    file_paths = get_all_file_paths(directory)

    print('\n [i] Following files will be zipped:')
    for file_name in file_paths:
        print(file_name)

    with open(manifest_file, "r") as manifest:
        manifest_data = json.load(manifest)

    name = manifest_data['name']
    version = manifest_data['version']
    file_name = name + '-' + version + '.zip'

    zip_file_dest = os.path.join(release_path, file_name)
    # compresslevel=9 for python37+
    with zipfile.ZipFile(zip_file_dest, 'w', compression=zipfile.ZIP_DEFLATED) as zip:
        for file in file_paths:
            zip.write(file, arcname=os.path.relpath(file, start=directory))

    print(' [i] All files zipped successfully!')


def buildUI(q):
    """
    Build Script for AIC-UI
    :param args: queue to store return data
    """
    _process_ui = Popen('npm run build', cwd='modules/aic-ui',
                        shell=True, stdout=PIPE, stderr=STDOUT)
    _output, _error = _process_ui.communicate()
    _process_ui.stdout.close()
    _returncode = _process_ui.wait()
    q.put(("UI", _returncode, _output.decode("utf8").strip()))


def buildBG(q, buildType="prod"):
    """
    Build Script for AIC-BG
    :param args: queue to store return data, args for build type
    """
    _build_cmd = f'npm run build-{buildType}'
    _process_bg = Popen(_build_cmd, cwd='modules/aic-bg',
                        shell=True, stdout=PIPE, stderr=STDOUT)
    _output, _error = _process_bg.communicate()
    _process_bg.stdout.close()
    _returncode = _process_bg.wait()
    q.put(("BG", _returncode, _output.decode("utf8").strip()))


def build_ui_utils_login(q):
    """
    Build Script for AIC-UTILS-LOGIN
    :param args: queue to store return data
    """
    _process_ui = Popen('npm run build', cwd='modules/aic-ui-utils/aic_login',
                        shell=True, stdout=PIPE, stderr=STDOUT)
    _output, _error = _process_ui.communicate()
    _process_ui.stdout.close()
    _returncode = _process_ui.wait()
    q.put(("UI_UTILS_LOGIN", _returncode, _output.decode("utf8").strip()))


def build_ui_utils_settings(q):
    """
    Build Script for AIC-UTILS_SETTINGS
    :param args: queue to store return data
    """
    _process_ui = Popen('npm run build', cwd='modules/aic-ui-utils/aic_settings',
                        shell=True, stdout=PIPE, stderr=STDOUT)
    _output, _error = _process_ui.communicate()
    _process_ui.stdout.close()
    _returncode = _process_ui.wait()
    q.put(("UI_UTILS_SETTINGS", _returncode, _output.decode("utf8").strip()))


def clear_build_dir():
    """
    Clear Build Directory for UI and BG
    """
    _patterns = [r'modules\extension\static\**\*', r'modules\extension\*background.bundle*.js',
                 r'modules\extension\login.html', r'modules\extension\settings.html', r'modules\extension\*src.*.js', r'modules\extension\*src.*.css',  r'modules\extension\*src.*.map']
    _files = []

    for p in _patterns:
        _files.extend(glob.glob(p, recursive=True))

    for f in _files:
        if(os.path.isfile(f)):
            os.remove(f)
    print(" [i] Cleared Build files for UI and BG from Extension")


def copy_build_files(support):
    """
    Copy the UI, BG and Support Builds content into extension
    """
    extension_dir = 'modules/extension'
    static_ext_dir = "modules/extension/static"

    copy_tree("modules/aic-ui/build/static", static_ext_dir)
    shutil.copy('modules/aic-ui/build/index.html', extension_dir)
    copy_tree('modules/aic-bg/build', extension_dir)

    if(support):
        copy_tree('modules/aic-ui-utils/aic_login/dist/', extension_dir)
        copy_tree('modules/aic-ui-utils/aic_settings/dist/',
                  extension_dir)
    print(' [i] Build files copied in extension folder for BG and UI')


if __name__ == '__main__':
    """
    Main method which takes command line args and process the build script
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-g', '--genesys', default='stage',
                        help='define the genesys url type')
    parser.add_argument('-o', '--okta',  default='stage',
                        help='define the okta url type')
    parser.add_argument('-e', '--extension', default='stage',
                        help='define the extension url type')
    parser.add_argument('-v', '--version',
                        help='define the extension version')
    parser.add_argument('-c', '--clean', action='store_true')
    parser.add_argument('-w', '--chrome-store', action='store_true')
    parser.add_argument('-d', '--dev', action='store_true')
    parser.add_argument('-s', '--support', action='store_true')
    parser.add_argument('-r', '--release', action='store_true')
    parser.add_argument('-z', '--zip', action='store_true')
    parser.add_argument('-n', '--nowrite', action='store_true')

    args = parser.parse_args()
    process_code = 0
    if(args.nowrite == False):
        process_code = write_files(args)

    zip_run = True
    if process_code == 0:
        clear_build_dir()
        q = queue.Queue()
        threads = []

        ui = Thread(target=buildUI, args=(q,))
        threads.append(ui)
        ui.start()

        bgBuildType = "prod"
        if args.support:
            bgBuildType = "support"
        elif args.dev:
            bgBuildType = "dev"

        bg = Thread(target=buildBG, args=(q, bgBuildType))
        threads.append(bg)
        bg.start()

        if(args.support):
            ui_utils_login = Thread(target=build_ui_utils_login, args=(q,))
            threads.append(ui_utils_login)
            ui_utils_login.start()

            ui_utils_settings = Thread(
                target=build_ui_utils_settings, args=(q,))
            threads.append(ui_utils_settings)
            ui_utils_settings.start()

        for t in threads:
            t.join()

        while q.empty() == False:
            _type, _return_code, _output = q.get()
            print(f"\n [i] Build {_type} :-  {_output}")
            if _return_code != 0:
                zip_run = False

    copy_build_files(args.support)
    if zip_run and args.zip:
        zip()
        print(" [i] Process Completed Succesfully")
    else:
        print(" [i] Zip is not selected or one/both of the build failed")
