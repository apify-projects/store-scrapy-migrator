# Apify Scrapy Migrator
This tool enables you to run scrapy project on Apify Cloud.

## Usage <hr>

### First run
- install the package - `pip install apify-scrapy-migrator`
- locate your scrapy project and migrate - `apify-scrapy-migrator -m DESTINATION`

### Upload to Apify cloud
There are multiple ways how to do it. You can copy your source files to Apify Cloud manually or import code via Github. But it is recommended to use Apify CLI.
- install Apify CLI. Guide [here](https://docs.apify.com/cli#installation).
- log in with your account - `apify login`
- go to your migrated project - `cd DESTINATION`
- push your project to Apify Cloud - `apify push`

### Update migration files
- If you want to update every file - `apify-scrapy-migrator -m DESTINATION`
- If you want to update your input - `apify-scrapy-migrator -i DESTINATION`
- If you want to update `requirements.txt` - `apify-scrapy-migrator -r DESTINATION`
