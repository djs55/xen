(*
 * Copyright (C) 2006-2007 XenSource Ltd.
 * Copyright (C) 2008      Citrix Ltd.
 * Author Vincent Hanquez <vincent.hanquez@eu.citrix.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published
 * by the Free Software Foundation; version 2.1 only. with the special
 * exception on linking described in file LICENSE.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *)

exception Reconnect

let _ =
  Callback.register_exception "Xs_ring.Reconnect" Reconnect

external read: Xenmmap.mmap_interface -> string -> int -> int = "ml_interface_read"
external write: Xenmmap.mmap_interface -> string -> int -> int = "ml_interface_write"

external set_server_features: Xenmmap.mmap_interface -> int -> unit = "ml_interface_set_server_features" "noalloc"
external get_server_features: Xenmmap.mmap_interface -> int = "ml_interface_get_server_features" "noalloc"

external close: Xenmmap.mmap_interface -> unit = "ml_interface_close" "noalloc"
