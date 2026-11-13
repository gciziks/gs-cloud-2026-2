resource "random_string" "sufixo" {
  length  = 5
  lower   = true
  upper   = false
  numeric = true
  special = false
}
