# ClassifyDocs

Classify a document using a large language model (LLM) into a set of predefined categories:

 - Acuerdo marco
 - Adjudicación de licitación
 - Albaran / Nota de entrega
 - Contrato
 - Factura
 - Pedido
 - Pliego
 - Quotation / oferta

## Construction and implementation

```shell
# Build image
docker compose build

# Resume service
docker compose up -d

# See logs
docker compose logs -f classifier
```

### Regenerate the container 

```shell
# Stops containers and removes containers, networks, volumes, and images created by up .
docker compose down -v   

docker compose build
docker compose up -d
docker compose logs -f classifier
```

## REST API exposed

 - Base URL: http://localhost:8000
 - Methods:
   - [POST] classifydoc: Classify a document using a large language model (LLM) into a set of predefined categories
     - Body params:
       - file: Path to the file to be classified

## Swagger documentation

Swagger documentation is available on this URL [http://localhost:8000/docs](http://localhost:8000/docs), 
when the container is up. 

![Swagger documentation](images/document-classifier-api.png)

## Test the REST API from the command line

```shell
#  Example using curl 
curl -X POST "http://localhost:8000/classifydoc" -F "file=@/ruta/a/tu/documento.pdf"
```