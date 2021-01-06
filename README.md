# Stats on third-party dependencies

This will retrieve statistics on third-party dependencies between two releases of Diem-core (c81923774ac832f2a9f9d28381f32212b3643b1c and
7ffca62b16313208033f3396dd5ec66a335d50a5).

To run this:

```sh
$ ./metrics.sh
$ python metrics.py
```

This should print something like:

```sh
- not including in analysis: ed25519-dalek 1.0.0 (git+https://github.com/novifinancial/ed25519-dalek.git?branch=fiat4#44d1191bb2aedf18418071992848fd8028e89b35)
- not including in analysis: x25519-dalek 1.0.1 (git+https://github.com/novifinancial/x25519-dalek.git?branch=fiat3#494bf274940818b1896d0492fcf2c66a2ee50736)
- not including in analysis: curve25519-dalek 3.0.0 (git+https://github.com/novifinancial/curve25519-dalek.git?branch=fiat3#2940429efd0e6482af1531cff079e6605cbc9cf2)
obtaining info from crates.io...
computing metrics...
92 dependencies were updated on the repo, jumping versions 179 increments higher.
Eventually, this can be summarized as
- 23 MINOR changes
- 67 PATCH changes
- 2 MAJOR changes
384 dependencies were analyzed in our codebase during that time period, which published 234 new versions
Eventually, this can be summarized as
- 7 MINOR changes
- 42 PATCH changes
- 3 MAJOR changes
- 1 PRERELEASE changes
```
