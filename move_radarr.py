#!/usr/bin/env python
import argparse
import requests
import urllib3
import logging

# Setup logging
LOG_LEVEL = logging.INFO  # Change this to your desired log level
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
parser = argparse.ArgumentParser()
parser.add_argument('--url', type=str, default="http://localhost:7878/api/v3",
                    help='The API URL and port of your Radarr instance')
parser.add_argument('--api', type=str,
                    help='The API key for your instance', required=True)
parser.add_argument('--tag', type=str,
                    help='The tag to search for', required=True)
parser.add_argument('--ignore-tag', type=str, nargs='+', dest='ignored_tags',
                    help='Ignore the movie if it contains one of the tags in this collection. Example: --exclude-tag ignore_move_script documentary')
parser.add_argument('--root', type=str,
                    help='The root folder to assign the found movies with the specified tag. Needs to exist in Radarr.', required=True)
parser.add_argument('--test', type=str, default=None,
                    help='Enter the title of a single movie for testing purposes')
args = parser.parse_args()

# Headers for API requests
headers = {
    'X-Api-Key': args.api
}

# Log request and response details
def log_request_response(response):
    logging.debug(f"Request URL: {response.request.url}")
    logging.debug(f"Request Method: {response.request.method}")
    logging.debug(f"Request Headers: {response.request.headers}")
    if response.request.body:
        logging.debug(f"Request Body: {response.request.body}")
    logging.debug(f"Response Status Code: {response.status_code}")
    logging.debug(f"Response Content: {response.text}")

# Get the list of movies from Radarr
def get_movies():
    logging.info("Fetching movies from Radarr...")
    url = f"{args.url}/movie"
    response = requests.get(url, headers=headers, verify=False)
    log_request_response(response)
    return response.json()

# Get the list of tags from Radarr
def get_tags():
    logging.info("Fetching tags from Radarr...")
    url = f"{args.url}/tag"
    response = requests.get(url, headers=headers, verify=False)
    log_request_response(response)
    return {tag['id']: tag['label'] for tag in response.json()}

# Get root folders from Radarr
def get_root_folders():
    logging.info("Fetching root folders from Radarr...")
    url = f"{args.url}/rootfolder"
    response = requests.get(url, headers=headers, verify=False)
    log_request_response(response)
    return response.json()

# Find the root folder id for a specific tag and root folder path
def find_tag_root_folder_id(root_folders, tag_name, new_root_folder_path):
    logging.info(f"Finding root folder ID for {new_root_folder_path}...")
    for folder in root_folders:
        if folder['path'] == new_root_folder_path:
            return folder['id']
    return None

# Update the movie root folder and path
def update_movie_root_folder(movie, new_root_folder_id, new_root_folder_path):
    logging.info(f"Updating root folder for movie: {movie['title']}")
    movie['rootFolderPath'] = new_root_folder_path
    movie['rootFolderId'] = new_root_folder_id
    movie['path'] = f"{new_root_folder_path}/{movie['title']}"  # Update the path as well

    url = f"{args.url}/movie/{movie['id']}"
    response = requests.put(
        url,
        json=movie,
        headers=headers,
        params={'moveFiles': True},
        verify=False
    )
    log_request_response(response)
    return response.status_code

# Main script execution
def main():
    movies_list = get_movies()
    tags = get_tags()
    root_folders = get_root_folders()
    tag_id = next((id for id, label in tags.items() if label == args.tag), None)
    ignored_tag_ids = [id for id, label in tags.items() if label in args.ignored_tags]
    
    if tag_id is None:
        logging.error(f"Could not find the tag '{args.tag}'.")
        return
    
    if len(ignored_tag_ids) != len(args.ignored_tags):
        logging.error(f"One or more ignored tags could not be found. Please check the configured tags. found {[label for _, label in tags.items() if label in args.ignored_tags]} but expected {args.ignored_tags}")
        return
    
    if not next((x for x in root_folders if x['path'] == args.root), None):
        logging.error(f"Could not find the root folder '{args.root}'.")
        return
    
    for movie in movies_list:
        if not args.test or movie['title'] == args.test:
            logging.debug(f"Processing movie: {movie['title']}")
            tags = movie.get('tags', [])
            if tag_id in tags and args.root in movie['rootFolderPath']:
                # Check if the new root folder path is contained in the existing root folder path
                logging.debug(f"Movie '{movie['title']}' is already in the correct root folder.")
            elif len([id for id in tags if id in ignored_tag_ids]) > 0:
                logging.debug(f"Ignoring movie '{movie['title']}' because it contains an ignored tag.")
            elif tag_id in tags:
                status_code = update_movie_root_folder(movie, tag_id, args.root)
                if status_code == 202:
                    logging.info(f"Successfully updated root folder for movie: {movie['title']}")
                else:
                    logging.error(f"Failed to update movie: {movie['title']} - Status Code: {status_code}")
            else:
                logging.debug(f"Movie '{movie['title']}' does not have the '{args.tag}' tag.")

if __name__ == "__main__":
    main()