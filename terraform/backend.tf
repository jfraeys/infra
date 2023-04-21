terraform {
  backend "local" {
    path = "state/terraform.tfstate"
  }
  #   backend "s3" {
  #     endpoint                    = "us-east-1.linodeobjects.com"
  #     skip_credentials_validation = true
  #     bucket                      = "blizzard"
  #     profile                     = "linode-s3"
  #     key                         = "infra/state.json"
  #     region                      = "us-east-1"
  #   }
}
