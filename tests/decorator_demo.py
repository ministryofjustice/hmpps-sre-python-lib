import pytest


# 1. A standard function
def my_test_function():
  return 'I ran!'


# 2. Applying a decorator manually
# This is exactly what @pytest.mark.slow does behind the scenes.
# It takes the function, adds a "slow" label to it, and returns it.
my_test_function_marked = pytest.mark.slow(my_test_function)

# We can inspect what happened clearly
if __name__ == '__main__':
  print(f'Original function name: {my_test_function.__name__}')

  # Check if the mark was applied
  # Pytest stores marks in a list called 'pytestmark' on the function object
  if hasattr(my_test_function_marked, 'pytestmark'):
    print('Marks found on function:')
    for mark in my_test_function_marked.pytestmark:
      print(f' - {mark.name}')

  # This is also how parametrize works without the @ syntax
  # It wraps the function to run multiple times
  def val_test(x):
    print(f'Testing value: {x}')

  # Manual parametrization
  # This creates a "Metafunc" that pytest can read
  parametrized_test = pytest.mark.parametrize('x', [1, 2, 3])(val_test)

  print('\nParametrize object created manually.')
