Steps to follow :- 



Create IAM user with S3 full acess and get acess & secret key for the user


Create a bucket name inside a region and create a empty .csv which will be uset to overwrite the forecast.


Set up the access &secret key,regionid,bucketname,.csv file name (for overwriting the forecast) inside both main.py and Live_market_notebook.ipynb.


Set up main.py and requirment.txt inside a Ec2 instance.


Install the libraries inside requirment.txt


Run main.py in Ec2 instance.


After 20 min you can run Live_market_notebook.ipynb to compare the forecast with actual stock price or index value
 along with past values for the same.
