package trivy

default ignore = false

# pip 26.2 vendors only pkg_resources from setuptools 70.3.0, so the
# setuptools advisories do not apply to code present in pip's private copy.
ignore {
    input.VulnerabilityID == "CVE-2025-47273"
    input.PkgIdentifier.BOMRef == "pkg:pypi/setuptools@70.3.0"
}

ignore {
    input.VulnerabilityID == "CVE-2026-59890"
    input.PkgIdentifier.BOMRef == "pkg:pypi/setuptools@70.3.0"
}

# pip's cache code does not use msgpack's vulnerable streaming Unpacker path.
ignore {
    input.VulnerabilityID == "GHSA-6v7p-g79w-8964"
    input.PkgIdentifier.BOMRef == "pkg:pypi/msgpack@1.1.2"
}
