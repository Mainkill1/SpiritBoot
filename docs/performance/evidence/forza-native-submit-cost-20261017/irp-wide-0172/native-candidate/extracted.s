	.file	"extracted.c"
	.text
	.globl	IopClearIrpPacket
	.type	IopClearIrpPacket, @function
IopClearIrpPacket:
	pushl	%ebp
	movl	%esp, %ebp
	pushl	%edi
	pushl	%ebx
	movl	8(%ebp), %edx
	movl	12(%ebp), %ebx
	movl	%edx, %eax
	movl	%ebx, %ecx
	andl	$3, %eax
	jne	.L2
	shrw	$2, %cx
	movl	%edx, %edi
	movzwl	%cx, %ecx
#APP
# 63 "docs/performance/evidence/forza-native-submit-cost-20261017/irp-wide-0172/native-candidate/extracted.c" 1
	rep stosl
# 0 "" 2
#NO_APP
	movl	%ebx, %ecx
	movl	%edi, %edx
	andl	$3, %ecx
.L2:
	movzwl	%cx, %ecx
	xorl	%eax, %eax
	movl	%edx, %edi
	rep stosb
	popl	%ebx
	popl	%edi
	popl	%ebp
	ret
	.size	IopClearIrpPacket, .-IopClearIrpPacket
	.globl	IoInitializeIrp
	.type	IoInitializeIrp, @function
IoInitializeIrp:
	pushl	%ebp
	movl	%esp, %ebp
	pushl	%esi
	pushl	%ebx
	subl	$24, %esp
	movl	12(%ebp), %esi
	movl	16(%ebp), %eax
	movzwl	%si, %edx
	movl	8(%ebp), %ebx
	movl	%eax, -12(%ebp)
	pushl	%edx
	pushl	%ebx
	call	IopClearIrpPacket
	movl	-12(%ebp), %eax
	movw	$6, (%ebx)
	movb	%al, 36(%ebx)
	movw	%si, 2(%ebx)
	leal	1(%eax), %edx
	addl	$16, %esp
	movsbl	%al, %eax
	imull	$36, %eax, %eax
	movb	%dl, 37(%ebx)
	movb	current_thread, %dl
	leal	72(%ebx,%eax), %eax
	movb	%dl, 38(%ebx)
	movl	%eax, 68(%ebx)
	leal	20(%ebx), %eax
	movl	%eax, 24(%ebx)
	movl	%eax, 20(%ebx)
	leal	-8(%ebp), %esp
	popl	%ebx
	popl	%esi
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
