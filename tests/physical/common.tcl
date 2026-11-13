# Shared formatting only. Safe to source in ordinary Tcl tests.
namespace eval physical {
    proc clean {value} {
        return [string map [list "\t" {\t} "\r" {\r} "\n" {\n}] $value]
    }
    proc row {handle values} {
        set cells {}
        foreach value $values {
            # Quote TSV fields so native metadata containing quotes is lossless.
            lappend cells [format {"%s"} [string map [list {"} {""}] [clean $value]]]
        }
        puts $handle [join $cells "\t"]
    }
    proc table {path header} {
        file mkdir [file dirname $path]
        set handle [open $path w]
        fconfigure $handle -encoding utf-8
        row $handle $header
        return $handle
    }
    proc exact_filter {name} {
        return [string map {{[} {\[} {]} {\]}} $name]
    }
}
