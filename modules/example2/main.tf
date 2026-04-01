resource "null_resource" "example2" {
  triggers = {
    value = "test-monorepo"
  }
}
