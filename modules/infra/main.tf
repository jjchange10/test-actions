resource "null_resource" "infra" {
  triggers = {
    value = "test-infra-release-notes-format"
  }
}
