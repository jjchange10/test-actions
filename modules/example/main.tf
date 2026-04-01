resource "null_resource" "example" {
  triggers = {
    value = "test-after-reset-test"
  }
}
