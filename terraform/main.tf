terraform {
  required_providers {
    linode = {
      source  = "linode/linode"
      version = "1.29.4"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "2.23.0"
    }
  }
}

provider "linode" {
  token = var.token
}

provider "docker" {
    host = "unix://var/run/docker.sock"
}

variable "token" {}

variable "linode_s3_access_key" {}

variable "linode_s3_secret_key" {}

resource "linode_instance" "atomic_instance" {
  region = "ca-central"
  type   = "g6-nanode-1"

  config {
    kernel       = "linode/grub2"
    label        = "My Ubuntu 20.04 LTS Disk Profile"
    memory_limit = 0
    root_device  = "/dev/sda"
    run_level    = "default"
    virt_mode    = "paravirt"

    devices {
      sda {
        disk_id    = 69721899
        disk_label = "Ubuntu 20.04 LTS Disk"
        volume_id  = 0
      }

      sdb {
        disk_id    = 69721900
        disk_label = "512 MB Swap Image"
        volume_id  = 0
      }
    }

    helpers {
      devtmpfs_automount = true
      distro             = true
      modules_dep        = true
      network            = true
      updatedb_disabled  = true
    }
  }

  disk {
    authorized_keys  = []
    authorized_users = []
    filesystem       = "ext4"
    label            = "Ubuntu 20.04 LTS Disk"
    read_only        = false
    size             = 25088
    stackscript_id   = 0
  }
  disk {
    authorized_keys  = []
    authorized_users = []
    filesystem       = "swap"
    label            = "512 MB Swap Image"
    read_only        = false
    size             = 512
    stackscript_id   = 0
  }
}


