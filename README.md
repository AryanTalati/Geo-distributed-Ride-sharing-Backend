# Geo-Distributed Ride-Sharing Database System

### You can either run locally or on cloud. This project is designed to be run on cloud.

## Run Locally

## Setup Python Project

Create a virtual environment:

```bash
python -m venv venv
```

Activate the virtual environment:

On Windows:

```bash
venv\Scripts\activate
```

On Linux/Mac:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run FastAPI Server

Start the FastAPI development server:

```bash
fastapi dev server/main.py
```

The API will be available at `http://localhost:8000`

## Initialize the CockroachDB Clusters

Start docker container:

```bash
docker-compose up -d
```

Initialize the cluster (Run this once):

```bash
docker exec -it roach-east-1 ./cockroach init --insecure
```

Open `localhost:8080` in browser to visualize the CockroachDB dashboard.

## Create Database and Assign Regions

Open CockroachDB shell inside the Docker container:

```bash
docker exec -it roach-east-1 ./cockroach sql --insecure
```

You need an enterprise license to enable multi-region features in CockroachDB.

Set the license key in roach shell:

```sql
SET CLUSTER SETTING enterprise.license = 'YOUR-CRDB-KEY-HERE';
```

Create Database:

```sql
CREATE DATABASE rideshare;
```

Assign a primary region:

```sql
ALTER DATABASE rideshare PRIMARY REGION "us-east";
```

Assign secondary regions:

```sql
ALTER DATABASE rideshare ADD REGION "us-west";
ALTER DATABASE rideshare ADD REGION "eu-central";
ALTER DATABASE rideshare ADD REGION "ap-south";
```

## Environment Configuration

The system supports two environments: `local` and `cloud`. Configure the environment using environment variables.

### Setup Environment Variables

Create a `.env` file from the sample:

```bash
cp .env.sample .env
```

Edit the `.env` file and set the appropriate values:

**For Local Environment:**

```bash
ENVIRONMENT=local
```

**For Cloud Environment:**

```bash
ENVIRONMENT=cloud
US_EAST_HOST=your-us-east-host.com
US_EAST_PORT=26257
US_WEST_HOST=your-us-west-host.com
US_WEST_PORT=26257
EU_CENTRAL_HOST=your-eu-central-host.com
EU_CENTRAL_PORT=26257
AP_SOUTH_HOST=your-ap-south-host.com
AP_SOUTH_PORT=26257
DATABASE_NAME=rideshare
DB_USER=your_username
DB_PASSWORD=your_password
```

Load environment variables (if using python-dotenv):

```bash
pip install python-dotenv
```

Then add this at the top of your scripts or export variables manually:

```bash
export $(cat .env | xargs)
```

On Windows PowerShell:

```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') } }
```

## Generate Data

Generate sample data:

```bash
python data_generation.py
```

Note: When `ENVIRONMENT=cloud`, the script generates data in lakhs (hundreds of thousands) per region. For local environment, it generates smaller test datasets.

## Load Data

Load sample data:

```bash
python load_generated_data.py
```

To delete data and load again:

```bash
python load_generated_data.py --clear
```

To just delete data from database:

```bash
python load_generated_data.py --delete-only
```

## Run on Cloud

### Setup EC2 Instances

Launch 4 EC2 instances in different AWS regions:

-   **us-east-1** (US East - N. Virginia)
-   **us-west-1** (US West - N. California)
-   **eu-central-1** (Europe - Frankfurt)
-   **ap-south-1** (Asia Pacific - Mumbai)

On each EC2 instance:

1. Install Docker:

```bash
sudo apt-get update
sudo apt-get install -y docker.io
sudo usermod -aG docker $USER
```

2. Configure Security Groups for each EC2 instance:

Open ports:

-   `2377` (Docker Swarm management)
-   `7946` (Docker Swarm node communication)
-   `4789` (Docker Swarm overlay network)
-   `26257` (CockroachDB)
-   `8080` (CockroachDB Admin UI)
-   `22` (SSH)

Allow inbound traffic from other EC2 instances' private IPs.

### Setup Docker Swarm

On the first EC2 instance (us-east-1), initialize Docker Swarm:

```bash
docker swarm init --advertise-addr <PUBLIC_IP_NODE_1>
```

Save the join token command that is displayed.

On the other three EC2 instances, join the swarm:

```bash
docker swarm join \
  --token <YOUR_TOKEN> \
  --advertise-addr <PUBLIC_IP_NODE_<N>> \
  <PUBLIC-IP-NODE-1>:2377
```

Verify all nodes are connected:

```bash
docker node ls
```

Now we need to tell docker which node represents which geographic region. This allows database to know where it is physically located.

```bash
docker node update --label-add region=us-east roach-east-1 <NODE-1-ID>
docker node update --label-add region=us-west roach-west-1 <NODE-2-ID>
docker node update --label-add region=eu-central roach-eu-central-1 <NODE-3-ID>
docker node update --label-add region=ap-south roach-ap-south-1 <NODE-4-ID>
```

Create a docker file:

```bash
nano docker-stack.yml
```

Copy and paste the docker-stack.yml file content.

Deploy the stack:

```bash
docker stack deploy -c docker-stack.yml rideshare
```

Verify the stack is deployed:

```bash
docker stack ps rideshare
```

Initialize the cluster:

```bash
    docker ps | grep roach-east-1
```

Grab the container ID and initialize the cluster

```bash
docker exec -it <CONTAINER_ID> ./cockroach init --insecure
```

### Setup regions

Get a container ID

```bash
docker ps | grep roach-east-1
```

Enter SQL

```bash
docker exec -it <CONTAINER_ID> ./cockroach sql --insecure
```

You need an enterprise license to enable multi-region features in CockroachDB.

Set the license key in roach shell:

```sql
SET CLUSTER SETTING enterprise.license = 'YOUR-CRDB-KEY-HERE';
```

Create Database:

```sql
CREATE DATABASE rideshare;
```

Assign a primary region:

```sql
ALTER DATABASE rideshare PRIMARY REGION "us-east";
```

Assign secondary regions:

```sql
ALTER DATABASE rideshare ADD REGION "us-west";
ALTER DATABASE rideshare ADD REGION "eu-central";
ALTER DATABASE rideshare ADD REGION "ap-south";
```

Verify the regions are assigned:

```sql
SHOW REGIONS FROM DATABASE rideshare;
```
