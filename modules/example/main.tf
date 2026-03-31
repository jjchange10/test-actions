resource "null_resource" "example" {
  triggers = {
    value = "verify-skip-release-test"
  }
}
