data "linode_object_storage_cluster" "primary" {
  id = "us-east-1"
}

resource "linode_object_storage_key" "blizzard_object_key" {
  label = "blizzard_services_terraform"
}

resource "linode_object_storage_bucket" "blizzard_object_bucket" {
  cluster = data.linode_object_storage_cluster.primary.id
  label   = "blizzard"
}

# For now in blizzard but change if needed.
resource "linode_object_storage_bucket" "state_object_bucket" {
  cluster = data.linode_object_storage_cluster.primary.id
  label   = "blizzard"
}


