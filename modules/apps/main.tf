resource "null_resource" "apps" {
  triggers = {
    value = "test-node24-update"
  }
}
