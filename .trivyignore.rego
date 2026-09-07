package trivy

default ignore = false

# pip 26.2.1's embedded BOM declares setuptools 70.3.0, but pip vendors only
# pkg_resources. The vulnerable PackageIndex code is not present in the image.
ignore {
    input.VulnerabilityID == "CVE-2025-47273"
    input.PkgIdentifier.BOMRef == "pkg:pypi/setuptools@70.3.0"
}

# pip 26.2.1 vendors msgpack's pure-Python fallback, while this advisory affects
# the compiled streaming Unpacker path that pip neither ships nor invokes.
ignore {
    input.VulnerabilityID == "GHSA-6v7p-g79w-8964"
    input.PkgIdentifier.BOMRef == "pkg:pypi/msgpack@1.1.2"
}
