# Construction and implementation

```shell
# Build image
docker compose build

# Resume service
docker compose up -d

# See logs
docker compose logs -f classifier
```


```shell
#  Example using curl 
curl -X POST "http://localhost:8000/classifydoc" -F "file=@/ruta/a/tu/documento.pdf"
```