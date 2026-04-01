resource "null_resource" "apps" {
  triggers = {
    value = "test-changed-files"
  }
}
