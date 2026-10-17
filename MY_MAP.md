MY_MAP: POST /listings/audit

Example listing: gtin = "123456789"

Step1: Validation is done by validation.py and the Jason formate is validateed if it is similar to ProductListing the way we want. 
Step 2: The listing faces recall_check.py ===> It checks the gtin agaest rapex_blacklist.json and if it is a match instant rejection 
Step 3: The listing goes through hygiene_check.py, it check if the listing has all the compulsary field according to GSPR and then flag it and pass forward if not field shows that it failed hygine_check so not complient 