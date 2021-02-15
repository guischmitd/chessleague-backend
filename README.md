# ACL backend
Python/Flask Backend for the dedicated Awogh Chess League WebApp.

## Installation
- Create a virtual environment
- Install requirements with `pip install -r requirements.txt`
- Use the `.env_sample` file as a template for your own `.env` file including the required API IDs and Secrets.
- `flask run` for hosting locally and debugging. Default address is http://127.0.0.1:5000

### .ENV variables
1. Create a lichess OAuth App key pair and plug the keys like so:
```
LICHESS_CLIENT_ID=<Client_ID>
LICHESS_CLIENT_SECRET=<Client_Secret>
```

2. Install postgres server, create a new database and link it as well:
```
SQLALCHEMY_DATABASE_URI = 'postgres+psycopg2://<USER_NAME>:<PASSWORD>@<DOMAIN>:<PORT, default is 5432>/<DB_NAME>'
```

3. Profit.

