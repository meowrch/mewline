# Maintainer: Ваше имя <email>
pkgname=mewline
pkgver=1.0  # Укажите актуальную версию
pkgrel=1
pkgdesc="StatusBar for meowrch"
arch=('any')
url="https://github.com/meowrch/mewline"
license=('MIT')
depends=('python' 'uv')
makedepends=('python-build' 'python-installer' 'python-wheel')
source=("$pkgname-$pkgver.tar.gz")  # Локальный архив проекта
sha256sums=('SKIP')

build() {
    cd "$pkgname"
    python -m build --wheel --no-isolation
}

package() {
  cd "$pkgname"
  python -m installer --destdir="$pkgdir" dist/*.whl
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
