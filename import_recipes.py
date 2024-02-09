import json
import os
import shelve
import time

import configargparse

from tandoor import TandoorAPI


def parse_args():
    parser = configargparse.ArgParser(
        config_file_parser_class=configargparse.ConfigparserConfigFileParser,
        ignore_unknown_config_file_keys=True,
        description='Add recipes converted from images by ChatGPT to Tandoor.'
    )
    # application related switches
    parser.add_argument('-c', '--my-config', is_config_file=True, default='config.ini', help='Specify configuration file.')
    parser.add_argument('--input_folder', default='import', help='Folder with screenshots of recipes.')
    parser.add_argument('--output_folder', default='out', help='Folder with json documents created by ChatGPT from screenshots.')
    parser.add_argument('--tandoor_url', type=str, required=True, help='The full url of the Tandoor server, including protocol, name, port and path')
    parser.add_argument('--tandoor_token', type=str, required=True, help='Tandoor API token.')
    parser.add_argument('--recipe_food', action='store_true', default=False, help='Create food representation of the recipe.')

    args = parser.parse_args()
    return args

def reportError(msg, image, details):
    print(f"{image}: {msg}")
    print(details)


args = parse_args()
input_dir = args.input_folder
output_dir = args.output_folder

api = TandoorAPI(args.tandoor_url, args.tandoor_token)
RECIPE_FOOD = args.recipe_food

try:
    caches = shelve.open('caches.db', writeback=True)
except FileNotFoundError:
    caches = {}

for img_name in os.listdir(input_dir):
    if img_name in caches:
        print(f"Skipping {img_name}, recipe already created.")
        continue

    json_path = os.path.join(output_dir, os.path.splitext(img_name)[0] + ".png.json")

    with open(os.path.join(input_dir, img_name),"rb") as img_file:
        image = (img_name, img_file.read(), None)
    with open(json_path) as f:
        json_data = {'data': f.read()}
        json_data['data'] = json_data['data'].replace('```json','')
        json_data['data'] = json_data['data'].replace('```','')
        json_data['data'] = json_data['data'].replace(',\n',',')
        json_data['data'] = json_data['data'].replace('{\n','{')
        json_data['data'] = json_data['data'].replace('\n}','}')
        json_data['data'] = json_data['data'].replace('[\n', '[')
        json_data['data'] = json_data['data'].replace('"\n','"')
        json_data['data'] = json_data['data'].replace("'", r"\u0027")
        json_data['data'] = json_data['data'].replace(r"Park\u00ed\u00fur", r"'P\u00fcr\u2022bk\u00f6r Pear'")
        json_data['data'] = json_data['data'].replace('"title":', '"name":')

    success, recipe = api.get_recipe_from_json(json_data)
    if not success:
        reportError('Failed to convert json to a recipe.', img_name, recipe)
        continue
    else:
        recipe=recipe['recipe_json']
    if not recipe['name']:
        reportError('Recipe has no name.', img_name, recipe)
        continue

    success, image = api.create_file(recipe["name"], image)
    if not success:
        reportError('Failed to create image', img_name, image)
        continue

    recipe["steps"][0]["file"] = image

    success, response = api.create_recipe(recipe)
    if not success:
        reportError('Failed to create recipe', img_name, response)
        continue

    if RECIPE_FOOD:
        success, response = api.create_food(response)
        if not success:
            reportError('Failed to create recipe as food', img_name, response)
            continue

    caches[img_name] = {'recipe': recipe['name']}
    caches.sync()