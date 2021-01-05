set +e

RELEASE1=c81923774ac832f2a9f9d28381f32212b3643b1c
RELEASE2=7ffca62b16313208033f3396dd5ec66a335d50a5

# get diem
git clone git@github.com:diem/diem.git diem
git clone --depth 1 git@github.com:diem/diem.git diem_latest
cd diem

# get stats on first release
git checkout $RELEASE1
cargo x generate-summaries
cp target/summaries/summary-release.toml ../release1.json

# get stats on second release
git checkout $RELEASE2
cargo x generate-summaries
cp target/summaries/summary-release.toml ../release2.json

# compare
cd ../diem_latest
cargo x diff-summary ../release1.json ../release2.json json > ../guppy_output.json

# save dates as well
cd ../diem
git show --no-patch --no-notes --pretty='%cd' --date=iso $RELEASE1 > ../release1.datetime
git show --no-patch --no-notes --pretty='%cd' --date=iso $RELEASE2 > ../release2.datetime
