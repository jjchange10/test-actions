resource "null_resource" "apps" {
  triggers = {
    value = "test-release-notes-format"
  }
}
