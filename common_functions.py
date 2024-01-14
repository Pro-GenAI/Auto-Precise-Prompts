# Copyright (c) 2024 Praneeth Vadlapati

import json
import os
import re
import time

from dotenv import load_dotenv
import openai
import pyperclip

load_dotenv(override=True)  # bypass cache and reload the variables

backtick = '`'
backticks = backtick * 3

def remove_spaces_after_commas(csv_text):
	# Regular expression to match commas followed by spaces not inside quotes
	pattern = re.compile(r'\s*,\s*(?=(?:[^"]*"[^"]*")*[^"]*$)')
	return pattern.sub(',', csv_text)  # Replace the matched pattern with a comma

def extract_data(response, data_format=None):
	'''
	Extracts data from a given response string based on the specified data format.

	Parameters:
	response (str): The response string containing the data.
	data_format (str, optional): The expected format of the data ('csv' or 'json'). Defaults to None.

	Returns:
	str or dict: The extracted data in the specified format. Returns a string for 'csv' format and a dictionary for 'json' format.

	Raises:
	Exception: If no backticks are found in the response.
	Exception: If the expected data format is not found at the beginning of the extracted data.
	'''
	if backticks not in response:  # if still no backticks to extract data from
		raise Exception('No backticks found in the response')

	# get the value from last triple backticks ``` to next last one ````, as first 2 backticks contain code or other information
	last = response.rfind(backticks) - 1
	last_2 = response.rfind(backticks, 0, last) + len(backticks)
	response = response[last_2:last].strip()

	response = response.strip().strip(backtick).strip()
	if not response.startswith(data_format):
		raise Exception(f'Expected format "{data_format}" not found in the response {response[:6]}...')
	response = response[len(data_format):]

	if data_format == 'csv':
		response = remove_spaces_after_commas(response)
		# strip every line
		response = '\n'.join([line.strip() for line in response.split('\n')])
	elif data_format == 'json':
		# load only data by ignoring all indents
		response = json.loads(response)
	return response
 

base_url = os.getenv('LM_PROVIDER_BASE_URL').strip() or None
api_key = os.getenv('LM_API_KEY').strip() or None
model_small = os.getenv('SMALL_MODEL').strip() or None

base_url_large = os.getenv('LARGE_LM_PROVIDER_BASE_URL').strip() or None
api_key_large = os.getenv('LARGE_LM_API_KEY').strip() or None
model_large = os.getenv('LARGE_MODEL').strip() or None

client_small = openai.OpenAI(base_url=base_url, api_key=api_key)
client_large = openai.OpenAI(base_url=base_url_large, api_key=api_key_large) \
					if model_large else None

def get_lm_response(messages, max_retries=4, use_large_model=False, model=None):
	'''
	Calls the Language Model API to get a response for the given messages.
	Example:
	.. code-block:: python
		message = 'Classify the following text based on predefined categories related to content safety.'
		response = get_bot_response(message)

		### or use message history array
		messages = [{'role': 'user', 'content': 'Classify the following text based on content safety categories.'}]
		response = get_bot_response(messages)
	'''
	client = client_small
	if use_large_model:  # decide the model
		model = model_large
		client = client_large
		print(f'Calling Large Model: {model}')
	
		if not model_large:  # if no model is mentioned, ask user to manually get response
			pyperclip.copy(messages)  # write message to clipboard
			response = input('Press Enter after copying response...').strip() or pyperclip.paste().strip()
			if not response:
				raise Exception('Empty response copied to clipboard')
			if messages == response:
				raise Exception('No response copied to clipboard')
			return response

	elif not model:  # default model
		model = model_small
 
	if isinstance(messages, str):
		messages = [{'role': 'user', 'content': messages}]

	for _ in range(max_retries):
		response = None
		try:
			response = client.chat.completions.create(messages=messages, model=model)
			response = response.choices[0].message.content.strip()
			if not response:
				raise Exception('Empty response from the bot')

			return response
		except Exception as e:
			e = str(e)
			if '429' in e:  # Rate limit
				total_wait_time = None
				if 'Please retry after' in e:  # Please retry after X sec
					total_wait_time = e.split('Please retry after')[1].split('sec')[0].strip()
					print(f'Rate Limit reached. Waiting for {total_wait_time} seconds. ', end='')
					total_wait_time = int(total_wait_time) + 1
				elif 'Please try again in' in e:  # 'Please try again in 23m3s. ...'
					rate_limit_time = e.split('Please try again in')[1].split('.')[0].strip()
					print(f'Rate Limit reached for {rate_limit_time}. ', end='', flush=True)
	 				# rate_limit_time = '1m20s'
					rate_limit_time_min = 0
					rate_limit_time_sec = 0
					if 'm' in rate_limit_time:
						rate_limit_time_min = rate_limit_time.split('m')[0]
						rate_limit_time = rate_limit_time.split('m')[1]  # get text after 'm'
					if 's' in rate_limit_time:
						rate_limit_time_sec = rate_limit_time.split('s')[0]
					total_wait_time = (int(rate_limit_time_min) * 60) + int(rate_limit_time_sec) + 1
				else:
					print(e)
					total_wait_time = 60
					print(f'Rate Limit reached with unknown wait time. Waiting for {total_wait_time} seconds. ', end='')
				print('Waiting', end='', flush=True)
				time.sleep(int(total_wait_time))
			elif '503' in e:  # Service Unavailable
				print('Service Unavailable. Waiting', end='', flush=True)
				time.sleep(15)
			else:
				print(f'Error: {e}. Retrying')
	raise Exception(f'No response from the bot after {max_retries} retries')



def print_progress():
	# Print a dot to indicate progress, without which the user might think the program is stuck
	print('.', end='', flush=True)

def print_error(err=None):
	# Indicate an error with an exclamation mark
	print('!', end='', flush=True)

