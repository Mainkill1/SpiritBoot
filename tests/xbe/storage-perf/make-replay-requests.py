#!/usr/bin/env python3
"""Render public operation metadata into a build-only C initializer."""
import argparse,csv,pathlib
def render(path):
    with pathlib.Path(path).open(newline='') as stream: rows=list(csv.DictReader(stream))
    if len(rows)!=2048:raise ValueError('replay needs exactly two complete 1024-operation schedules')
    operations=[]
    for position,row in enumerate(rows):
        dataset,index,offset,length,alignment=(int(row[key]) for key in ['dataset','index','offset','length','alignment'])
        if (dataset!=position//1024 or index!=position%1024 or offset<0 or offset%512
                or length<=0 or length>65536 or length%512 or not 0<=alignment<4096):
            raise ValueError('invalid or reordered public replay operation')
        operations.append((offset,length,alignment))
    return ('/* Generated public request metadata only; no game content. */\n'
            'static const struct Request { ULONG offset, length, alignment; } requests[] = {\n'
            +''.join(f'    {{{offset}, {length}, {alignment}}},\n' for offset,length,alignment in operations)+'};\n')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',default='replay-requests.csv');parser.add_argument('--output',default='replay-requests.h');args=parser.parse_args()
    pathlib.Path(args.output).write_text(render(args.input))
if __name__=='__main__':main()
