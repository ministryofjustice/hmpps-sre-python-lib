import pytest
import os
from src.hmpps.clients.service_catalogue import ServiceCatalogue


@pytest.fixture(scope='class')
def sc_client():
  sc_params = {
    'url': os.getenv('SERVICE_CATALOGUE_API_ENDPOINT'),
    'key': os.getenv('SERVICE_CATALOGUE_API_KEY'),
    'filter': os.getenv('SC_FILTER', ''),
  }
  yield ServiceCatalogue(sc_params)
  print('done')
