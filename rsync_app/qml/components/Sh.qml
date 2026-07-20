pragma Singleton
import QtQuick

// POSIX shell quoting for surfaced rsync commands. The runner executes
// the argv directly (no shell), so quoting changes nothing about what
// runs — it makes the displayed/copied string paste-safe, so a path
// with spaces or a glob in an --exclude runs identically in a terminal.
QtObject {
    function quote(argv) {
        return (argv || []).map(a => _quoteOne(String(a))).join(" ")
    }

    function _quoteOne(a) {
        if (a !== "" && /^[A-Za-z0-9_@%+=:,.\/-]+$/.test(a)) return a
        return "'" + a.replace(/'/g, "'\\''") + "'"
    }
}
