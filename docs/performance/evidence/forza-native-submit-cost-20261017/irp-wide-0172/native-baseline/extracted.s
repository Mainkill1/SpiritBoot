	.file	"extracted.c"
	.text
	.globl	IoInitializeIrp
	.type	IoInitializeIrp, @function
IoInitializeIrp:
	pushl	%ebp
	xorl	%eax, %eax
	movl	%esp, %ebp
	pushl	%edi
	pushl	%esi
	pushl	%ebx
	movl	8(%ebp), %edx
	movl	12(%ebp), %esi
	movl	16(%ebp), %ebx
	movzwl	%si, %ecx
	movl	%edx, %edi
	rep stosb
	movb	%bl, 36(%edx)
	leal	1(%ebx), %eax
	movsbl	%bl, %ebx
	imull	$36, %ebx, %ebx
	movb	%al, 37(%edx)
	movb	current_thread, %al
	movb	%al, 38(%edx)
	leal	72(%edx,%ebx), %eax
	movl	%eax, 68(%edx)
	leal	20(%edx), %eax
	movw	$6, (%edx)
	movw	%si, 2(%edx)
	movl	%eax, 24(%edx)
	movl	%eax, 20(%edx)
	popl	%ebx
	popl	%esi
	popl	%edi
	popl	%ebp
	ret
	.size	IoInitializeIrp, .-IoInitializeIrp
	.globl	IoReuseIrp
	.type	IoReuseIrp, @function
IoReuseIrp:
	pushl	%ebp
	movl	%esp, %ebp
	pushl	%esi
	pushl	%ebx
	movl	8(%ebp), %ebx
	movzbl	39(%ebx), %esi
	pushl	%eax
	movsbl	36(%ebx), %eax
	pushl	%eax
	movzwl	2(%ebx), %eax
	pushl	%eax
	pushl	%ebx
	call	IoInitializeIrp
	movl	12(%ebp), %eax
	addl	$16, %esp
	movl	%eax, 28(%ebx)
	movl	%esi, %eax
	movb	%al, 39(%ebx)
	leal	-8(%ebp), %esp
	popl	%ebx
	popl	%esi
	popl	%ebp
	ret
	.size	IoReuseIrp, .-IoReuseIrp
	.ident	"GCC: (Debian 14.2.0-19) 14.2.0"
	.section	.note.GNU-stack,"",@progbits
