/*
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
 */

#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>

#include <xenctrl.h>
#include <xen/io/xs_wire.h>

#include <caml/mlvalues.h>
#include <caml/memory.h>
#include <caml/alloc.h>
#include <caml/custom.h>
#include <caml/fail.h>
#include <caml/callback.h>

#include "mmap_stubs.h"

#define GET_C_STRUCT(a) ((struct mmap_interface *) a)

#define ERROR_UNKNOWN (-1)
#define ERROR_CLOSING (-2)

static int xs_ring_read(struct mmap_interface *interface,
                             char *buffer, int len)
{
	struct xenstore_domain_interface *intf = interface->addr;
	XENSTORE_RING_IDX cons, prod; /* offsets only */
	int to_read;
	uint32_t closing;

	cons = *(volatile uint32*)&intf->req_cons;
	prod = *(volatile uint32*)&intf->req_prod;
	closing = *(volatile uint32*)&intf->closing;

	if (closing != 0)
		return ERROR_CLOSING;

	xen_mb();

	if ((prod - cons) > XENSTORE_RING_SIZE)
	    return ERROR_UNKNOWN;

	if (prod == cons)
		return 0;
	cons = MASK_XENSTORE_IDX(cons);
	prod = MASK_XENSTORE_IDX(prod);
	if (prod > cons)
		to_read = prod - cons;
	else
		to_read = XENSTORE_RING_SIZE - cons;
	if (to_read < len)
		len = to_read;
	memcpy(buffer, intf->req + cons, len);
	xen_mb();
	intf->req_cons += len;
	return len;
}

static int xs_ring_write(struct mmap_interface *interface,
                              char *buffer, int len)
{
	struct xenstore_domain_interface *intf = interface->addr;
	XENSTORE_RING_IDX cons, prod;
	int can_write;
	uint32_t closing;

	cons = *(volatile uint32*)&intf->rsp_cons;
	prod = *(volatile uint32*)&intf->rsp_prod;
	closing = *(volatile uint32*)&intf->closing;

	if (closing != 0)
		return ERROR_CLOSING;

	xen_mb();
	if ( (prod - cons) >= XENSTORE_RING_SIZE )
		return 0;
	if (MASK_XENSTORE_IDX(prod) >= MASK_XENSTORE_IDX(cons))
		can_write = XENSTORE_RING_SIZE - MASK_XENSTORE_IDX(prod);
	else 
		can_write = MASK_XENSTORE_IDX(cons) - MASK_XENSTORE_IDX(prod);
	if (can_write < len)
		len = can_write;
	memcpy(intf->rsp + MASK_XENSTORE_IDX(prod), buffer, len);
	xen_mb();
	intf->rsp_prod += len;
	return len;
}

CAMLprim value ml_interface_read(value interface, value buffer, value len)
{
	CAMLparam3(interface, buffer, len);
	CAMLlocal1(result);
	int res;

	res = xs_ring_read(GET_C_STRUCT(interface),
	                   String_val(buffer), Int_val(len));
	if (res == ERROR_UNKNOWN)
		caml_failwith("bad connection");

	if (res == ERROR_CLOSING)
		caml_raise_constant(*caml_named_value("Xs_ring.Closing"));

	result = Val_int(res);
	CAMLreturn(result);
}

CAMLprim value ml_interface_write(value interface, value buffer, value len)
{
	CAMLparam3(interface, buffer, len);
	CAMLlocal1(result);
	int res;

	res = xs_ring_write(GET_C_STRUCT(interface),
	                    String_val(buffer), Int_val(len));

	if (res == ERROR_CLOSING)
		caml_raise_constant(*caml_named_value("Xs_ring.Closing"));

	result = Val_int(res);
	CAMLreturn(result);
}

CAMLprim value ml_interface_set_server_version(value interface, value v)
{
	CAMLparam2(interface, v);
	struct xenstore_domain_interface *intf = GET_C_STRUCT(interface)->addr;

	intf->server_version = Int_val(v);

	CAMLreturn(Val_unit);
}

CAMLprim value ml_interface_get_server_version(value interface)
{
	CAMLparam1(interface);
	struct xenstore_domain_interface *intf = GET_C_STRUCT(interface)->addr;

	CAMLreturn(Val_int (intf->server_version));
}

CAMLprim value ml_interface_close(value interface)
{
	CAMLparam1(interface);
	const char invalid_data[] = { 'd', 'e', 'a', 'd', 'b', 'e', 'e', 'f' };
	struct xenstore_domain_interface *intf = GET_C_STRUCT(interface)->addr;
	int i;

	intf->req_cons = intf->req_prod = intf->rsp_cons = intf->rsp_prod = 0;
	/* Ensure the unused space is full of invalid xenstore packets. */
	for (i = 0; i < XENSTORE_RING_SIZE; i++) {
		intf->req[i] = invalid_data[i % sizeof(invalid_data)];
		intf->rsp[i] = invalid_data[i % sizeof(invalid_data)];
	}
	xen_mb ();
	intf->closing = 0;
	CAMLreturn(Val_unit);
}
