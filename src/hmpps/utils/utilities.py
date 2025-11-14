def update_dict(this_dict, key, sub_dict):
  """
  Updates a dictionary by merging a sub-dictionary into a nested dictionary at a specified key.

  If the key does not exist in the dictionary, it is initialized with an empty dictionary before updating.

  Args:
    this_dict (dict): The dictionary to update.
    key (hashable): The key whose value will be updated with sub_dict.
    sub_dict (dict): The dictionary to merge into this_dict[key].

  Returns:
    None: The function modifies this_dict in place.
  """
  if key not in this_dict:
    this_dict[key] = {}
  this_dict[key].update(sub_dict)


def fetch_yaml_values_for_key(yaml_data, key):
  """
  Recursively searches through a nested YAML data structure (dicts and lists)
  and collects all values associated with the specified key.

  Args:
    yaml_data (dict or list): The YAML data to search, typically loaded from a YAML file.
    key (str): The key to search for within the YAML data.

  Returns:
    dict: A dictionary containing all found values for the specified key.
        If the value for the key is a dictionary, its contents are merged.
        If the value is not a dictionary, it is added under the key.
        Nested results are grouped under their parent keys.

  Example:
    >>> yaml_data = {
    ...     'config': {'timeout': 30, 'retries': 3},
    ...     'service': {'timeout': 10},
    ...     'list': [{'timeout': 5}, {'other': 1}]
    ... }
    >>> fetch_yaml_values_for_key(yaml_data, 'timeout')
    {'config': {'timeout': 30}, 'service': {'timeout': 10}, 'timeout': 5}
  """
  values = {}
  if isinstance(yaml_data, dict):
    if key in yaml_data:
      if isinstance(yaml_data[key], dict):
        values.update(yaml_data[key])
      else:
        values[key] = yaml_data[key]
    for k, v in yaml_data.items():
      if isinstance(v, (dict, list)):
        child_values = fetch_yaml_values_for_key(v, key)
        if child_values:
          values.update({k: child_values})
  elif isinstance(yaml_data, list):
    for item in yaml_data:
      child_values = fetch_yaml_values_for_key(item, key)
      if child_values:
        values.update(child_values)

  return values


def find_matching_keys(data, search_key):
  """
  Recursively searches for all values associated with a specified key in a nested dictionary or list structure.

  Args:
    data (dict or list): The data structure to search, which may contain nested dictionaries and/or lists.
    search_key (str): The key to search for within the data structure.

  Returns:
    list: A list of all values found that are associated with the specified key.
  """
  found_values = []

  if isinstance(data, dict):
    for key, value in data.items():
      if key == search_key:
        found_values.append(value)
      else:
        found_values.extend(find_matching_keys(value, search_key))
  elif isinstance(data, list):
    for item in data:
      found_values.extend(find_matching_keys(item, search_key))

  return found_values
