import pytest
from src.hmpps.clients.service_catalogue import ServiceCatalogue


@pytest.fixture(scope='class')
def sc_client():
  yield ServiceCatalogue()
  print('done')
