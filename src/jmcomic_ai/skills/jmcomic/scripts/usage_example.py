from jmcomic_ai.core import JmcomicService

# Initialize service
service = JmcomicService()

# Search
results = service.search_album("search_keyword")
print(f"Found {len(results)} albums.")

# Download first result
if results:
    first_album = results[0]
    print(f"Downloading {first_album['title']}...")
    service.download_album(first_album["id"])
